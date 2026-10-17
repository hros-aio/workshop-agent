"""Project progress overview for monitors (US8)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workshop.common.enums import (
    DocumentStatus,
    ItemState,
    ProjectStatus,
    ValidationOutcome,
)
from workshop.document.models import WorkshopDocument
from workshop.export.models import WorkshopExportPackage
from workshop.project.models import WorkshopProject
from workshop.project.schemas import ProjectOverview
from workshop.proposal.service import item_state_counts
from workshop.validation.service import latest_validation_run


def build_overview(session: Session, project: WorkshopProject) -> ProjectOverview:
    counts = item_state_counts(session, project.id)
    normalized = {
        "pending": counts.get(ItemState.PENDING.value, 0),
        "accepted": counts.get(ItemState.ACCEPTED.value, 0),
        "rejected": counts.get(ItemState.REJECTED.value, 0),
        "modified": counts.get(ItemState.MODIFIED.value, 0),
        "conflicts": counts.get("conflicts", 0),
        "assumptions": counts.get("assumptions", 0),
    }

    doc_counts = dict(
        session.execute(
            select(WorkshopDocument.status, func.count())
            .where(WorkshopDocument.project_id == project.id)
            .group_by(WorkshopDocument.status)
        ).all()
    )
    documents = {
        "active": doc_counts.get(DocumentStatus.UPLOADED.value, 0) + doc_counts.get(DocumentStatus.ANALYZED.value, 0),
        "superseded": doc_counts.get(DocumentStatus.SUPERSEDED.value, 0),
        "parseFailed": doc_counts.get(DocumentStatus.PARSE_FAILED.value, 0),
    }

    run = latest_validation_run(session, project.id)
    validation = None
    if run is not None:
        validation = {
            "overallResult": run.overall_result,
            "triggeredAt": run.triggered_at,
            "passed": run.overall_result == ValidationOutcome.PASS.value,
        }

    last_version = session.scalar(
        select(func.max(WorkshopExportPackage.version_number)).where(WorkshopExportPackage.project_id == project.id)
    )

    return ProjectOverview(
        project_id=project.id,
        status=ProjectStatus(project.status),
        current_round=project.current_round,
        item_counts=normalized,
        validation=validation,
        document_counts=documents,
        last_export_version=last_version,
    )
