"""Arq worker task: process one Analysis Run.

Fail-loud semantics: any AI/provider/schema failure marks the run Failed and
persists no proposal. Success persists the whole round in one transaction and
moves the project to `In Review`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from workshop.ai.factory import for_provider
from workshop.analysis.models import WorkshopAnalysisRun
from workshop.analysis.service import run_analysis
from workshop.audit import service as audit
from workshop.common.enums import (
    AnalysisRunStatus,
    AuditAction,
    ProjectStatus,
)
from workshop.logging import get_logger
from workshop.project.lifecycle import assert_transition
from workshop.project.models import WorkshopProject

logger = get_logger(__name__)


async def process_analysis_run(ctx: dict[str, Any], run_id: str) -> str:
    from workshop.db import get_session_factory

    session: Session = get_session_factory()()
    try:
        run = session.get(WorkshopAnalysisRun, uuid.UUID(run_id))
        if run is None:
            logger.warning("analysis.run_missing", run_id=run_id)
            return "missing"
        if run.status not in {
            AnalysisRunStatus.QUEUED.value,
            AnalysisRunStatus.RUNNING.value,
        }:
            return run.status

        project = session.get(WorkshopProject, run.project_id)
        if project is None:
            return "missing"

        run.status = AnalysisRunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)
        session.commit()

        try:
            ai = for_provider(run.ai_provider)
            proposal = run_analysis(session, project=project, run=run, ai=ai)

            run.status = AnalysisRunStatus.COMPLETED.value
            run.completed_at = datetime.now(UTC)
            assert_transition(ProjectStatus.IN_ANALYSIS.value, ProjectStatus.IN_REVIEW.value)
            project.status = ProjectStatus.IN_REVIEW.value

            audit.record(
                session,
                tenant_id=project.tenant_id,
                action=AuditAction.ANALYSIS_COMPLETED,
                project_id=project.id,
                entity_type="AnalysisRun",
                entity_id=run.id,
                payload={"roundNumber": run.round_number},
            )
            audit.record(
                session,
                tenant_id=project.tenant_id,
                action=AuditAction.PROPOSAL_GENERATED,
                project_id=project.id,
                entity_type="Proposal",
                entity_id=proposal.id,
                payload={"roundNumber": proposal.round_number},
            )
            audit.record(
                session,
                tenant_id=project.tenant_id,
                action=AuditAction.STATUS_TRANSITION,
                project_id=project.id,
                entity_type="Project",
                entity_id=project.id,
                payload={"from": ProjectStatus.IN_ANALYSIS.value, "to": ProjectStatus.IN_REVIEW.value},
            )
            session.commit()
            return "completed"
        except Exception as exc:
            session.rollback()
            run = session.get(WorkshopAnalysisRun, uuid.UUID(run_id))
            project = session.get(WorkshopProject, run.project_id) if run else None
            if run is not None:
                run.status = AnalysisRunStatus.FAILED.value
                run.completed_at = datetime.now(UTC)
                run.error_message = str(exc)
            if project is not None:
                audit.record(
                    session,
                    tenant_id=project.tenant_id,
                    action=AuditAction.ANALYSIS_FAILED,
                    project_id=project.id,
                    entity_type="AnalysisRun",
                    entity_id=run.id if run else None,
                    payload={"error": str(exc)},
                )
            session.commit()
            logger.error("analysis.failed", run_id=run_id, error=str(exc))
            return "failed"
    finally:
        session.close()
