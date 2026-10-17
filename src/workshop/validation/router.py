"""Validation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.dependencies import get_current_user, get_db, require_project_role
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import FINALIZE_ROLES, VIEW_ROLES, AuditAction
from workshop.project.models import WorkshopProject
from workshop.validation import service
from workshop.validation.schemas import ValidationRun

router = APIRouter(tags=["Validation"])


def _to_schema(session: Session, run: object) -> ValidationRun:
    results = service.results_for_run(session, run.id)  # type: ignore[attr-defined]
    payload = ValidationRun.model_validate(
        {
            "id": run.id,  # type: ignore[attr-defined]
            "project_id": run.project_id,  # type: ignore[attr-defined]
            "round_number": run.round_number,  # type: ignore[attr-defined]
            "triggered_by": run.triggered_by,  # type: ignore[attr-defined]
            "triggered_at": run.triggered_at,  # type: ignore[attr-defined]
            "overall_result": run.overall_result,  # type: ignore[attr-defined]
            "results": results,
        }
    )
    return payload


@router.post("/projects/{project_id}/validation-runs", response_model=ValidationRun)
def run_validation(
    project: WorkshopProject = Depends(require_project_role(*FINALIZE_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ValidationRun:
    run = service.run_validation(
        session,
        project_id=project.id,
        round_number=project.current_round,
        triggered_by=user.user_id,
    )
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.VALIDATION_RUN,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="ValidationRun",
        entity_id=run.id,
        payload={"overallResult": run.overall_result, "roundNumber": run.round_number},
    )
    session.commit()
    return _to_schema(session, run)


@router.get(
    "/projects/{project_id}/validation-runs/latest",
    response_model=ValidationRun | None,
)
def get_latest_validation_run(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> ValidationRun | None:
    run = service.latest_validation_run(session, project.id)
    return _to_schema(session, run) if run is not None else None


@router.get(
    "/projects/{project_id}/validation-runs",
    response_model=list[ValidationRun],
)
def list_validation_runs(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[ValidationRun]:
    return [_to_schema(session, run) for run in service.list_validation_runs(session, project.id)]
