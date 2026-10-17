"""Shared helpers for integration tests."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from workshop.common.enums import (
    AIProvider,
    DocumentStatus,
    EntityType,
    ProjectRole,
    UploadStatus,
)
from workshop.document import storage
from workshop.document.models import WorkshopDocument, WorkshopDocumentVersion
from workshop.project.models import WorkshopProject, WorkshopProjectMember


def make_project(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    creator: uuid.UUID,
    scoped: list[EntityType] | None = None,
    provider: AIProvider = AIProvider.OPENAI,
) -> WorkshopProject:
    project = WorkshopProject(
        tenant_id=tenant_id,
        customer_id=uuid.uuid4(),
        name="Test Workshop",
        status="Setup",
        ai_provider=provider.value,
        scoped_entity_types=[e.value for e in (scoped or [EntityType.COMPANY])],
        created_by=creator,
    )
    session.add(project)
    session.flush()
    session.add(
        WorkshopProjectMember(
            project_id=project.id,
            user_id=creator,
            role=ProjectRole.CONSULTANT.value,
            added_by=creator,
        )
    )
    session.flush()
    return project


def add_member(session: Session, project: WorkshopProject, user_id: uuid.UUID, role: ProjectRole) -> None:
    session.add(WorkshopProjectMember(project_id=project.id, user_id=user_id, role=role.value, added_by=user_id))
    session.flush()


def add_uploaded_document(
    session: Session,
    project: WorkshopProject,
    *,
    uploaded_by: uuid.UUID,
    file_name: str,
    mime_type: str,
    data: bytes,
    document_type: str = "intake",
) -> WorkshopDocumentVersion:
    document = WorkshopDocument(
        project_id=project.id,
        document_type=document_type,
        status=DocumentStatus.UPLOADED.value,
        created_by=uploaded_by,
    )
    session.add(document)
    session.flush()

    version_id = uuid.uuid4()
    key = storage.build_key(
        tenant_id=project.tenant_id,
        project_id=project.id,
        document_id=document.id,
        version_id=version_id,
        file_name=file_name,
    )
    storage.upload_bytes(key, data, content_type=mime_type)

    version = WorkshopDocumentVersion(
        id=version_id,
        document_id=document.id,
        version_number=1,
        storage_key=key,
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        upload_status=UploadStatus.UPLOADED.value,
        uploaded_by=uploaded_by,
    )
    session.add(version)
    document.current_version_id = version_id
    session.flush()
    return version


def csv_bytes(rows: list[list[str]]) -> bytes:
    return ("\n".join(",".join(row) for row in rows) + "\n").encode("utf-8")


def seed_proposal_item(
    session: Session,
    project: WorkshopProject,
    *,
    entity_type: EntityType,
    entity_key: str,
    value: dict[str, Any],
    round_number: int = 1,
    has_conflict: bool = False,
    is_assumption: bool = False,
) -> uuid.UUID:
    """Create a proposal round + one item (no decision); returns the item id."""
    from workshop.analysis.models import WorkshopAnalysisRun
    from workshop.proposal.models import WorkshopProposal, WorkshopProposalItem

    run = WorkshopAnalysisRun(
        project_id=project.id,
        round_number=round_number,
        status="Completed",
        ai_provider=project.ai_provider,
        document_version_ids=[],
        triggered_by=project.created_by,
    )
    session.add(run)
    session.flush()
    proposal = WorkshopProposal(project_id=project.id, analysis_run_id=run.id, round_number=round_number)
    session.add(proposal)
    session.flush()
    item = WorkshopProposalItem(
        proposal_id=proposal.id,
        entity_type=entity_type.value,
        entity_key=entity_key,
        proposed_value=value,
        explanation="seed",
        confidence="High",
        is_assumption=is_assumption,
        has_conflict=has_conflict,
        source_refs=[],
    )
    session.add(item)
    session.flush()
    return item.id


def seed_accepted_item(
    session: Session,
    project: WorkshopProject,
    *,
    entity_type: EntityType,
    entity_key: str,
    value: dict[str, Any],
) -> uuid.UUID:
    """Create a single proposal round with one accepted item; returns item id."""
    from workshop.review.models import WorkshopDecision

    item_id = seed_proposal_item(session, project, entity_type=entity_type, entity_key=entity_key, value=value)
    session.add(
        WorkshopDecision(
            proposal_item_id=item_id,
            action="Accept",
            resulting_value=value,
            decided_by=uuid.uuid4(),
        )
    )
    session.flush()
    return item_id
