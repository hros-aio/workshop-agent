"""Export service: build the artifact set, upload all-or-nothing, version it."""

from __future__ import annotations

import hashlib
import uuid
from contextlib import suppress
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import (
    AuditAction,
    ProjectStatus,
    ValidationOutcome,
)
from workshop.common.errors import ConflictError, NotFoundError
from workshop.document import storage
from workshop.events import producer
from workshop.export.generators.decision_log import generate_decision_log
from workshop.export.generators.difference_report import generate_difference_report
from workshop.export.generators.excel_package import generate_entity_workbooks
from workshop.export.generators.validation_report import generate_validation_report
from workshop.export.models import WorkshopExportPackage
from workshop.project.lifecycle import assert_transition
from workshop.project.models import WorkshopProject
from workshop.proposal import service as proposal_service
from workshop.proposal.models import WorkshopProposal, WorkshopProposalItem
from workshop.review.models import WorkshopDecision
from workshop.validation import service as validation_service


def _next_version(session: Session, project_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(WorkshopExportPackage.version_number)).where(WorkshopExportPackage.project_id == project_id)
    )
    return (current or 0) + 1


def _decision_log_rows(session: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            WorkshopProposal.round_number,
            WorkshopProposalItem.entity_type,
            WorkshopProposalItem.entity_key,
            WorkshopDecision,
        )
        .join(WorkshopProposalItem, WorkshopProposalItem.proposal_id == WorkshopProposal.id)
        .join(WorkshopDecision, WorkshopDecision.proposal_item_id == WorkshopProposalItem.id)
        .where(WorkshopProposal.project_id == project_id)
        .order_by(WorkshopDecision.decided_at)
    ).all()
    return [
        {
            "round_number": round_number,
            "entity_type": entity_type,
            "entity_key": entity_key,
            "action": decision.action,
            "resulting_value": decision.resulting_value,
            "comment": decision.comment,
            "decided_by": decision.decided_by,
            "decided_at": decision.decided_at,
            "reopened": decision.reopened,
        }
        for round_number, entity_type, entity_key, decision in rows
    ]


def _build_artifacts(session: Session, project: WorkshopProject) -> tuple[dict[str, bytes], uuid.UUID]:
    validation_run = validation_service.latest_validation_run(session, project.id)
    if validation_run is None or validation_run.overall_result != ValidationOutcome.PASS.value:
        raise ConflictError("A passing validation run is required before exporting")

    dataset = proposal_service.accepted_dataset(session, project.id)
    artifacts = generate_entity_workbooks(dataset, project.scoped_entity_types)

    diff_name, diff_bytes = generate_difference_report(dataset)
    artifacts[diff_name] = diff_bytes

    results = validation_service.results_for_run(session, validation_run.id)
    val_name, val_bytes = generate_validation_report(validation_run, results)
    artifacts[val_name] = val_bytes

    log_name, log_bytes = generate_decision_log(_decision_log_rows(session, project.id))
    artifacts[log_name] = log_bytes

    return artifacts, validation_run.id


def create_export(session: Session, user: AuthenticatedUser, project: WorkshopProject) -> WorkshopExportPackage:
    if project.status != ProjectStatus.FINALIZED.value:
        raise ConflictError("Only a finalized project can be exported")

    artifacts, validation_run_id = _build_artifacts(session, project)

    version = _next_version(session, project.id)
    prefix = f"workshop/{user.tenant_id}/{project.id}/exports/v{version}/"

    uploaded: list[dict[str, str]] = []
    stored_keys: list[str] = []
    try:
        for name in sorted(artifacts):
            data = artifacts[name]
            key = f"{prefix}{name}"
            storage.upload_bytes(
                key,
                data,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            stored_keys.append(key)
            uploaded.append({"name": name, "key": key, "checksum": hashlib.sha256(data).hexdigest()})
    except Exception:
        for key in stored_keys:
            with suppress(Exception):
                storage.delete_object(key)
        raise

    package = WorkshopExportPackage(
        project_id=project.id,
        version_number=version,
        storage_prefix=prefix,
        files=uploaded,
        validation_run_id=validation_run_id,
        exported_by=user.user_id,
    )
    session.add(package)

    assert_transition(project.status, ProjectStatus.EXPORTED.value)
    project.status = ProjectStatus.EXPORTED.value

    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.EXPORT_GENERATED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="ExportPackage",
        entity_id=package.id,
        payload={"versionNumber": version, "files": [f["name"] for f in uploaded]},
    )
    session.flush()

    producer.emit_exported(
        project_id=project.id,
        tenant_id=user.tenant_id,
        package_version=version,
        storage_prefix=prefix,
    )
    return package


def list_exports(session: Session, project_id: uuid.UUID) -> list[WorkshopExportPackage]:
    return list(
        session.execute(
            select(WorkshopExportPackage)
            .where(WorkshopExportPackage.project_id == project_id)
            .order_by(WorkshopExportPackage.version_number.desc())
        )
        .scalars()
        .all()
    )


def get_export(session: Session, project_id: uuid.UUID, version_number: int) -> WorkshopExportPackage:
    package = (
        session.execute(
            select(WorkshopExportPackage).where(
                WorkshopExportPackage.project_id == project_id,
                WorkshopExportPackage.version_number == version_number,
            )
        )
        .scalars()
        .first()
    )
    if package is None:
        raise NotFoundError("Export package not found")
    return package


def file_download_url(package: WorkshopExportPackage, file_name: str) -> str:
    for entry in package.files:
        if entry["name"] == file_name:
            return storage.presigned_get_url(entry["key"])
    raise NotFoundError("Export file not found")
