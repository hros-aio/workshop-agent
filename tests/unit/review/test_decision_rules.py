"""Unit tests: decision comment/resulting-value rules and item resolution (T076)."""

from __future__ import annotations

import uuid

import pytest

from workshop.common.enums import DecisionAction, ItemState
from workshop.common.errors import DomainValidationError
from workshop.proposal.service import state_for
from workshop.review.schemas import DecisionCreate
from workshop.review.service import record_decision


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass


class _Item:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.entity_key = "Company:acme"
        self.proposed_value = {"name": "Acme"}


class _User:
    def __init__(self) -> None:
        self.user_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()


class _Project:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()


def test_reject_without_comment_rejected() -> None:
    with pytest.raises(DomainValidationError):
        record_decision(_Session(), _User(), _Project(), _Item(), DecisionCreate(action=DecisionAction.REJECT))


def test_modify_without_comment_rejected() -> None:
    with pytest.raises(DomainValidationError):
        record_decision(
            _Session(),
            _User(),
            _Project(),
            _Item(),
            DecisionCreate(action=DecisionAction.MODIFY, resulting_value={"name": "New"}),
        )


def test_modify_without_resulting_value_rejected() -> None:
    with pytest.raises(DomainValidationError):
        record_decision(
            _Session(),
            _User(),
            _Project(),
            _Item(),
            DecisionCreate(action=DecisionAction.MODIFY, comment="fix it"),
        )


def test_accept_without_comment_allowed_and_echoes_value() -> None:
    decision = record_decision(_Session(), _User(), _Project(), _Item(), DecisionCreate(action=DecisionAction.ACCEPT))
    assert decision.action == DecisionAction.ACCEPT.value
    assert decision.resulting_value == {"name": "Acme"}


def test_modify_records_resulting_value() -> None:
    decision = record_decision(
        _Session(),
        _User(),
        _Project(),
        _Item(),
        DecisionCreate(
            action=DecisionAction.MODIFY,
            resulting_value={"name": "Acme Corporation"},
            comment="expanded name",
        ),
    )
    assert decision.resulting_value == {"name": "Acme Corporation"}


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (DecisionAction.ACCEPT, ItemState.ACCEPTED),
        (DecisionAction.MODIFY, ItemState.MODIFIED),
        (DecisionAction.REJECT, ItemState.REJECTED),
    ],
)
def test_item_state_projection(action: DecisionAction, expected: ItemState) -> None:
    class _Decision:
        pass

    decision = _Decision()
    decision.action = action.value
    assert state_for(decision) == expected


def test_pending_state_when_no_decision() -> None:
    assert state_for(None) == ItemState.PENDING
