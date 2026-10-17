"""Analysis Run endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from workshop.analysis.models import WorkshopAnalysisRun
from workshop.analysis.schemas import AnalysisRun, AnalysisRunTrigger
from workshop.audit import service as audit
from workshop.auth.dependencies import get_current_user, get_db, require_project_role
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import (
    TRIGGER_ANALYSIS_ROLES,
    VIEW_ROLES,
    AnalysisRunStatus,
    AuditAction,
    ProjectStatus,
)
from workshop.common.errors import ConflictError, DomainValidationError, NotFoundError
from workshop.document.service import active_version_ids
from workshop.logging import get_logger
from workshop.project.lifecycle import assert_transition
from workshop.project.models import WorkshopProject

router = APIRouter(tags=["Analysis Runs"])
logger = get_logger(__name__)


async def _enqueue(run_id: uuid.UUID) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings

    from workshop.settings import get_settings

    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        await pool.enqueue_job("process_analysis_run", str(run_id))
        await pool.aclose()
    except Exception as exc:  # pragma: no cover - redis may be absent locally
        logger.warning("analysis.enqueue_failed", run_id=str(run_id), error=str(exc))


@router.post(
    "/projects/{project_id}/analysis-runs",
    response_model=AnalysisRun,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_analysis_run(
    data: AnalysisRunTrigger | None = None,
    project: WorkshopProject = Depends(require_project_role(*TRIGGER_ANALYSIS_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> AnalysisRun:
    running = (
        session.execute(
            select(WorkshopAnalysisRun).where(
                WorkshopAnalysisRun.project_id == project.id,
                WorkshopAnalysisRun.status.in_([AnalysisRunStatus.QUEUED.value, AnalysisRunStatus.RUNNING.value]),
            )
        )
        .scalars()
        .first()
    )
    if running is not None:
        raise ConflictError("An analysis run is already in progress")

    version_ids = active_version_ids(session, project.id)
    if not version_ids:
        raise DomainValidationError("There are no uploaded documents to analyze")

    round_number = project.current_round + 1
    run = WorkshopAnalysisRun(
        project_id=project.id,
        round_number=round_number,
        status=AnalysisRunStatus.QUEUED.value,
        ai_provider=project.ai_provider,
        document_version_ids=version_ids,
        triggered_by=user.user_id,
    )
    session.add(run)
    session.flush()

    previous = project.status
    assert_transition(previous, ProjectStatus.IN_ANALYSIS.value)
    project.status = ProjectStatus.IN_ANALYSIS.value

    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.ANALYSIS_TRIGGERED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="AnalysisRun",
        entity_id=run.id,
        payload={
            "roundNumber": round_number,
            "aiProvider": project.ai_provider,
            "documentVersionIds": [str(v) for v in version_ids],
        },
    )
    session.commit()

    await _enqueue(run.id)
    return AnalysisRun.model_validate(run)


@router.get("/projects/{project_id}/analysis-runs", response_model=list[AnalysisRun])
def list_analysis_runs(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[AnalysisRun]:
    runs = session.execute(
        select(WorkshopAnalysisRun)
        .where(WorkshopAnalysisRun.project_id == project.id)
        .order_by(WorkshopAnalysisRun.created_at.desc())
    ).scalars()
    return [AnalysisRun.model_validate(r) for r in runs]


@router.get("/projects/{project_id}/analysis-runs/{run_id}", response_model=AnalysisRun)
def get_analysis_run(
    run_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> AnalysisRun:
    run = session.get(WorkshopAnalysisRun, run_id)
    if run is None or run.project_id != project.id:
        raise NotFoundError("Analysis run not found")
    return AnalysisRun.model_validate(run)


@router.post(
    "/projects/{project_id}/analysis-runs/{run_id}/retry",
    response_model=AnalysisRun,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_analysis_run(
    run_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*TRIGGER_ANALYSIS_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> AnalysisRun:
    prior = session.get(WorkshopAnalysisRun, run_id)
    if prior is None or prior.project_id != project.id:
        raise NotFoundError("Analysis run not found")
    if prior.status != AnalysisRunStatus.FAILED.value:
        raise ConflictError("Only a failed analysis run can be retried")

    run = WorkshopAnalysisRun(
        project_id=project.id,
        round_number=prior.round_number,
        status=AnalysisRunStatus.QUEUED.value,
        ai_provider=prior.ai_provider,
        document_version_ids=prior.document_version_ids,
        triggered_by=user.user_id,
    )
    session.add(run)
    session.flush()
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.ANALYSIS_TRIGGERED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="AnalysisRun",
        entity_id=run.id,
        payload={"retryOf": str(prior.id)},
    )
    session.commit()
    await _enqueue(run.id)
    return AnalysisRun.model_validate(run)
