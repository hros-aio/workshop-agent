"""Review service: immutable decisions with comment and modify rules."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import AuditAction, DecisionAction
from workshop.common.errors import DomainValidationError, NotFoundError
from workshop.project.models import WorkshopProject
from workshop.proposal.models import WorkshopProposal, WorkshopProposalItem
from workshop.review.models import WorkshopDecision
from workshop.review.schemas import DecisionCreate


def get_item_for_project(session: Session, project_id: uuid.UUID, item_id: uuid.UUID) -> WorkshopProposalItem:
    item = session.get(WorkshopProposalItem, item_id)
    if item is None:
        raise NotFoundError("Proposal item not found")
    proposal = session.get(WorkshopProposal, item.proposal_id)
    if proposal is None or proposal.project_id != project_id:
        raise NotFoundError("Proposal item not found")
    return item


def record_decision(
    session: Session,
    user: AuthenticatedUser,
    project: WorkshopProject,
    item: WorkshopProposalItem,
    data: DecisionCreate,
) -> WorkshopDecision:
    if data.action in (DecisionAction.REJECT, DecisionAction.MODIFY) and (not data.comment or not data.comment.strip()):
        raise DomainValidationError(
            f"A comment is required for {data.action.value}",
            errors=[{"field": "comment", "message": "comment is required"}],
        )

    if data.action == DecisionAction.MODIFY:
        if data.resulting_value is None:
            raise DomainValidationError(
                "A resulting_value is required for Modify",
                errors=[{"field": "resulting_value", "message": "required for Modify"}],
            )
        resulting_value: dict[str, Any] = data.resulting_value
    else:
        # Accept and Reject echo the proposed value for the record.
        resulting_value = item.proposed_value

    decision = WorkshopDecision(
        proposal_item_id=item.id,
        action=data.action.value,
        resulting_value=resulting_value,
        comment=data.comment,
        decided_by=user.user_id,
    )
    session.add(decision)
    session.flush()

    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.DECISION_RECORDED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="ProposalItem",
        entity_id=item.id,
        payload={
            "action": data.action.value,
            "entityKey": item.entity_key,
            "comment": data.comment,
        },
    )
    return decision


def list_decisions(session: Session, item_id: uuid.UUID) -> list[WorkshopDecision]:
    from sqlalchemy import select

    return list(
        session.execute(
            select(WorkshopDecision)
            .where(WorkshopDecision.proposal_item_id == item_id)
            .order_by(WorkshopDecision.decided_at.desc())
        )
        .scalars()
        .all()
    )
