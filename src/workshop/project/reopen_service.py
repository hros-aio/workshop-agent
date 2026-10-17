"""Explicit, logged reopen of an exported project (US9)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import AuditAction, ProjectStatus
from workshop.common.errors import ConflictError
from workshop.project.models import WorkshopProject
from workshop.review.models import WorkshopDecision


def reopen_project(session: Session, user: AuthenticatedUser, project: WorkshopProject, reason: str) -> WorkshopProject:
    if project.status != ProjectStatus.EXPORTED.value:
        raise ConflictError("Only an exported project can be reopened")

    # Decisions made before the reopen are marked so the derived dataset excludes
    # them until they are re-decided; existing rows are never updated in place by
    # the review flow, this flag records that the reopen invalidated prior intent.
    session.execute(
        update(WorkshopDecision)
        .where(WorkshopDecision.proposal_item_id.in_(_project_item_ids(project.id)))
        .values(reopened=True)
    )

    project.status = ProjectStatus.IN_REVIEW.value
    project.reopen_count += 1
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.PROJECT_REOPENED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="Project",
        entity_id=project.id,
        payload={"reason": reason, "reopenCount": project.reopen_count},
    )
    return project


def _project_item_ids(project_id: object) -> Any:
    from workshop.proposal.models import WorkshopProposal, WorkshopProposalItem

    return (
        select(WorkshopProposalItem.id)
        .join(WorkshopProposal, WorkshopProposal.id == WorkshopProposalItem.proposal_id)
        .where(WorkshopProposal.project_id == project_id)
        .scalar_subquery()
    )
