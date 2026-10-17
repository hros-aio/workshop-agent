"""Unit tests for the fixed lifecycle transition table and guards."""

from __future__ import annotations

import pytest

from workshop.common.enums import ProjectStatus
from workshop.common.errors import ConflictError, InvalidTransitionError
from workshop.project.lifecycle import assert_transition


def test_setup_to_collecting_documents_allowed() -> None:
    assert_transition(ProjectStatus.SETUP.value, ProjectStatus.COLLECTING_DOCUMENTS.value)


def test_collecting_to_analysis_allowed() -> None:
    assert_transition(ProjectStatus.COLLECTING_DOCUMENTS.value, ProjectStatus.IN_ANALYSIS.value)


def test_review_back_edge_to_analysis_allowed() -> None:
    assert_transition(ProjectStatus.IN_REVIEW.value, ProjectStatus.IN_ANALYSIS.value)


def test_finalized_to_exported_allowed() -> None:
    assert_transition(ProjectStatus.FINALIZED.value, ProjectStatus.EXPORTED.value)


@pytest.mark.parametrize(
    ("frm", "to"),
    [
        (ProjectStatus.SETUP.value, ProjectStatus.IN_REVIEW.value),
        (ProjectStatus.SETUP.value, ProjectStatus.EXPORTED.value),
        (ProjectStatus.COLLECTING_DOCUMENTS.value, ProjectStatus.IN_REVIEW.value),
        (ProjectStatus.IN_ANALYSIS.value, ProjectStatus.FINALIZED.value),
        (ProjectStatus.FINALIZED.value, ProjectStatus.IN_REVIEW.value),
    ],
)
def test_disallowed_transitions_rejected(frm: str, to: str) -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition(frm, to)


def test_unknown_status_rejected() -> None:
    with pytest.raises(ConflictError):
        assert_transition("Nonsense", ProjectStatus.IN_REVIEW.value)
