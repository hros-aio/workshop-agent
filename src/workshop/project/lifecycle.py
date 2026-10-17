"""Fixed project lifecycle: an enum plus guard functions, not a workflow engine."""

from __future__ import annotations

from sqlalchemy.orm import Session

from workshop.common.enums import ProjectStatus, ValidationOutcome
from workshop.common.errors import ConflictError, InvalidTransitionError

ALLOWED_TRANSITIONS: dict[ProjectStatus, list[ProjectStatus]] = {
    ProjectStatus.SETUP: [ProjectStatus.COLLECTING_DOCUMENTS],
    ProjectStatus.COLLECTING_DOCUMENTS: [ProjectStatus.IN_ANALYSIS],
    ProjectStatus.IN_ANALYSIS: [ProjectStatus.IN_REVIEW],
    ProjectStatus.IN_REVIEW: [ProjectStatus.IN_ANALYSIS, ProjectStatus.FINALIZED],
    ProjectStatus.FINALIZED: [ProjectStatus.EXPORTED],
    ProjectStatus.EXPORTED: [ProjectStatus.IN_REVIEW],
}

# Reopen is a distinct, explicitly logged action, never a plain transition.
REOPEN_TRANSITION = (ProjectStatus.EXPORTED, ProjectStatus.IN_REVIEW)


def assert_transition(from_status: str, to_status: str) -> None:
    try:
        source = ProjectStatus(from_status)
        target = ProjectStatus(to_status)
    except ValueError as exc:
        raise InvalidTransitionError(from_status, to_status) from exc
    if target not in ALLOWED_TRANSITIONS.get(source, []):
        raise InvalidTransitionError(from_status, to_status)


def guard_finalize(session: Session, *, project_id: object) -> None:
    """Guard for `In Review -> Finalized`.

    Requires every item resolved (no pending/rejected) and the latest validation
    run to have passed. Imports are local to avoid import cycles.
    """
    from workshop.common.enums import ItemState
    from workshop.proposal.service import item_state_counts
    from workshop.validation.service import latest_validation_run

    counts = item_state_counts(session, project_id)  # type: ignore[arg-type]
    if counts.get(ItemState.PENDING.value, 0) or counts.get(ItemState.REJECTED.value, 0):
        raise ConflictError("All proposal items must be resolved before finalizing")

    run = latest_validation_run(session, project_id)  # type: ignore[arg-type]
    if run is None or run.overall_result != ValidationOutcome.PASS.value:
        raise ConflictError("A passing validation run is required before finalizing")


def guard_transition(session: Session, project: object, target_status: str) -> None:
    """Validate a requested transition, including state-specific guards."""
    from_status = project.status  # type: ignore[attr-defined]
    assert_transition(from_status, target_status)
    if target_status == ProjectStatus.IN_REVIEW.value and from_status == ProjectStatus.EXPORTED.value:
        raise ConflictError("Use the explicit reopen action to return an exported project to review")
    if target_status == ProjectStatus.FINALIZED.value:
        guard_finalize(session, project_id=project.id)  # type: ignore[attr-defined]
