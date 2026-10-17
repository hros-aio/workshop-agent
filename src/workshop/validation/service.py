"""Validation run orchestration over the accepted dataset."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from workshop.common.enums import (
    ItemState,
    ValidationOutcome,
)
from workshop.proposal.service import accepted_dataset, latest_items_per_key, state_for
from workshop.validation.base import ValidationContext, ValidationRuleResult
from workshop.validation.models import WorkshopValidationResult, WorkshopValidationRun
from workshop.validation.registry import get_rules

_RESOLVED = {ItemState.ACCEPTED, ItemState.MODIFIED}


def _open_items(session: Session, project_id: uuid.UUID, *, conflicts: bool) -> list[dict[str, Any]]:
    flagged: list[dict[str, Any]] = []
    for entity_key, (item, _round, decision) in latest_items_per_key(session, project_id).items():
        if state_for(decision) in _RESOLVED:
            continue
        if conflicts and not item.has_conflict:
            continue
        if not conflicts and not item.is_assumption:
            continue
        flagged.append({"entity_type": item.entity_type, "entity_key": entity_key})
    return flagged


def build_context(session: Session, project_id: uuid.UUID) -> ValidationContext:
    return ValidationContext(
        project_id=project_id,
        dataset=accepted_dataset(session, project_id),
        unresolved_conflicts=_open_items(session, project_id, conflicts=True),
        unacknowledged_assumptions=_open_items(session, project_id, conflicts=False),
    )


def run_validation(
    session: Session, *, project_id: uuid.UUID, round_number: int, triggered_by: uuid.UUID
) -> WorkshopValidationRun:
    context = build_context(session, project_id)
    results: list[ValidationRuleResult] = []
    for rule in get_rules():
        try:
            results.append(rule.evaluate(context))
        except Exception as exc:  # fail-loud per rule, never crash the whole run
            results.append(
                ValidationRuleResult(
                    rule_code=getattr(rule, "code", rule.__class__.__name__),
                    result=ValidationOutcome.FAIL,
                    failing_records=[{"detail": f"Rule raised: {exc}"}],
                )
            )

    overall = (
        ValidationOutcome.PASS if all(r.result == ValidationOutcome.PASS for r in results) else ValidationOutcome.FAIL
    )
    run = WorkshopValidationRun(
        project_id=project_id,
        round_number=round_number,
        triggered_by=triggered_by,
        overall_result=overall.value,
    )
    session.add(run)
    session.flush()
    for result in results:
        session.add(
            WorkshopValidationResult(
                validation_run_id=run.id,
                rule_code=result.rule_code,
                result=result.result.value,
                failing_records=result.failing_records or None,
            )
        )
    session.flush()
    return run


def latest_validation_run(session: Session, project_id: uuid.UUID) -> WorkshopValidationRun | None:
    return (
        session.execute(
            select(WorkshopValidationRun)
            .where(WorkshopValidationRun.project_id == project_id)
            .order_by(WorkshopValidationRun.triggered_at.desc(), WorkshopValidationRun.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def list_validation_runs(session: Session, project_id: uuid.UUID) -> list[WorkshopValidationRun]:
    return list(
        session.execute(
            select(WorkshopValidationRun)
            .where(WorkshopValidationRun.project_id == project_id)
            .order_by(WorkshopValidationRun.triggered_at.desc(), WorkshopValidationRun.id.desc())
        )
        .scalars()
        .all()
    )


def results_for_run(session: Session, validation_run_id: uuid.UUID) -> list[WorkshopValidationResult]:
    return list(
        session.execute(
            select(WorkshopValidationResult)
            .where(WorkshopValidationResult.validation_run_id == validation_run_id)
            .order_by(WorkshopValidationResult.rule_code)
        )
        .scalars()
        .all()
    )
