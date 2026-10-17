"""Proposal read model: accepted-dataset derivation, item state, locking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from workshop.common.enums import DecisionAction, ItemState
from workshop.proposal.models import WorkshopProposal, WorkshopProposalItem
from workshop.review.models import WorkshopDecision


@dataclass
class LockedItem:
    item_id: uuid.UUID
    entity_type: str
    entity_key: str
    proposed_value: dict[str, Any]
    explanation: str
    confidence: str
    is_assumption: bool
    source_refs: list[dict[str, Any]]


def _items_with_decision(
    session: Session, project_id: uuid.UUID
) -> list[tuple[WorkshopProposalItem, int, WorkshopDecision | None]]:
    rows = session.execute(
        select(WorkshopProposalItem, WorkshopProposal.round_number)
        .join(WorkshopProposal, WorkshopProposal.id == WorkshopProposalItem.proposal_id)
        .where(WorkshopProposal.project_id == project_id)
    ).all()
    decisions = _decisions_by_item(session, project_id)
    result: list[tuple[WorkshopProposalItem, int, WorkshopDecision | None]] = []
    for item, round_number in rows:
        result.append((item, round_number, decisions.get(item.id)))
    return result


def _decisions_by_item(session: Session, project_id: uuid.UUID) -> dict[uuid.UUID, WorkshopDecision]:
    rows = session.execute(
        select(WorkshopDecision)
        .join(WorkshopProposalItem, WorkshopProposalItem.id == WorkshopDecision.proposal_item_id)
        .join(WorkshopProposal, WorkshopProposal.id == WorkshopProposalItem.proposal_id)
        .where(WorkshopProposal.project_id == project_id)
        .order_by(WorkshopDecision.decided_at)
    ).scalars()
    latest: dict[uuid.UUID, WorkshopDecision] = {}
    for decision in rows:
        latest[decision.proposal_item_id] = decision  # last (newest) wins locally; full list still kept
    return latest


def state_for(decision: WorkshopDecision | None) -> ItemState:
    if decision is None:
        return ItemState.PENDING
    if decision.action == DecisionAction.ACCEPT.value:
        return ItemState.ACCEPTED
    if decision.action == DecisionAction.MODIFY.value:
        return ItemState.MODIFIED
    return ItemState.REJECTED


def latest_items_per_key(
    session: Session, project_id: uuid.UUID
) -> dict[str, tuple[WorkshopProposalItem, int, WorkshopDecision | None]]:
    """Latest item (highest round) per entity_key, with its latest decision."""
    selected: dict[str, tuple[WorkshopProposalItem, int, WorkshopDecision | None]] = {}
    for item, round_number, decision in _items_with_decision(session, project_id):
        current = selected.get(item.entity_key)
        if current is None or round_number > current[1] or round_number == current[1] and decision is not None:
            selected[item.entity_key] = (item, round_number, decision)
    return selected


def item_state_counts(session: Session, project_id: uuid.UUID) -> dict[str, int]:
    counts: dict[str, int] = {
        ItemState.PENDING.value: 0,
        ItemState.ACCEPTED.value: 0,
        ItemState.REJECTED.value: 0,
        ItemState.MODIFIED.value: 0,
        "conflicts": 0,
        "assumptions": 0,
    }
    for item, _round, decision in latest_items_per_key(session, project_id).values():
        counts[state_for(decision).value] += 1
        if item.has_conflict:
            counts["conflicts"] += 1
        if item.is_assumption:
            counts["assumptions"] += 1
    return counts


def accepted_dataset(session: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """Derived read model: latest Accept/Modify decision per entity_key."""
    selected = latest_items_per_key(session, project_id)
    dataset: list[dict[str, Any]] = []
    for entity_key, (item, _round, decision) in selected.items():
        if decision is None or decision.reopened:
            continue
        if decision.action not in (DecisionAction.ACCEPT.value, DecisionAction.MODIFY.value):
            continue
        dataset.append(
            {
                "entity_type": item.entity_type,
                "entity_key": entity_key,
                "resulting_value": decision.resulting_value,
                "decided_by": decision.decided_by,
                "decided_at": decision.decided_at,
                "source_refs": item.source_refs,
                "is_assumption": item.is_assumption,
                "has_conflict": item.has_conflict,
            }
        )
    return dataset


def locked_items(session: Session, project_id: uuid.UUID) -> list[LockedItem]:
    """Accepted/modified items carried forward unchanged into later rounds."""
    selected = latest_items_per_key(session, project_id)
    locked: list[LockedItem] = []
    for entity_key, (item, _round, decision) in selected.items():
        if decision is None or decision.reopened:
            continue
        if decision.action not in (DecisionAction.ACCEPT.value, DecisionAction.MODIFY.value):
            continue
        locked.append(
            LockedItem(
                item_id=item.id,
                entity_type=item.entity_type,
                entity_key=entity_key,
                proposed_value=decision.resulting_value,
                explanation=item.explanation,
                confidence=item.confidence,
                is_assumption=item.is_assumption,
                source_refs=item.source_refs,
            )
        )
    return locked


def rejected_keys(session: Session, project_id: uuid.UUID) -> set[str]:
    selected = latest_items_per_key(session, project_id)
    return {
        key
        for key, (_item, _round, decision) in selected.items()
        if decision is not None and decision.action == DecisionAction.REJECT.value
    }


def latest_proposal(session: Session, project_id: uuid.UUID) -> WorkshopProposal | None:
    return (
        session.execute(
            select(WorkshopProposal)
            .where(WorkshopProposal.project_id == project_id)
            .order_by(WorkshopProposal.round_number.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def proposal_by_round(session: Session, project_id: uuid.UUID, round_number: int) -> WorkshopProposal | None:
    return (
        session.execute(
            select(WorkshopProposal).where(
                WorkshopProposal.project_id == project_id,
                WorkshopProposal.round_number == round_number,
            )
        )
        .scalars()
        .first()
    )


def items_for_proposal(session: Session, proposal_id: uuid.UUID) -> list[WorkshopProposalItem]:
    return list(
        session.execute(
            select(WorkshopProposalItem)
            .where(WorkshopProposalItem.proposal_id == proposal_id)
            .order_by(WorkshopProposalItem.entity_type, WorkshopProposalItem.entity_key)
        )
        .scalars()
        .all()
    )


def decisions_for_items(session: Session, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, WorkshopDecision]:
    if not item_ids:
        return {}
    rows = session.execute(
        select(WorkshopDecision)
        .where(WorkshopDecision.proposal_item_id.in_(item_ids))
        .order_by(WorkshopDecision.decided_at)
    ).scalars()
    latest: dict[uuid.UUID, WorkshopDecision] = {}
    for decision in rows:
        latest[decision.proposal_item_id] = decision
    return latest
