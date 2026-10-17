"""Unit tests: reopen transitions and reopen_count (T105)."""

from __future__ import annotations

import uuid

import pytest

from workshop.common.enums import ProjectStatus
from workshop.common.errors import ConflictError
from workshop.project.reopen_service import reopen_project


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.executed: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def execute(self, statement: object) -> None:
        self.executed.append(statement)


class _User:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()


class _Project:
    def __init__(self, status: str) -> None:
        self.id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()
        self.status = status
        self.reopen_count = 0


def test_reopen_from_exported_returns_to_review_and_increments() -> None:
    project = _Project(ProjectStatus.EXPORTED.value)
    reopen_project(_Session(), _User(), project, "customer changed scope")
    assert project.status == ProjectStatus.IN_REVIEW.value
    assert project.reopen_count == 1


def test_reopen_from_non_exported_rejected() -> None:
    project = _Project(ProjectStatus.IN_REVIEW.value)
    with pytest.raises(ConflictError):
        reopen_project(_Session(), _User(), project, "nope")
    assert project.reopen_count == 0
