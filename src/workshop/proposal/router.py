"""Proposal endpoints: rounds, items, comparison, traceability."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from workshop.auth.dependencies import get_db, require_project_role
from workshop.common.enums import VIEW_ROLES, EntityType, ItemState
from workshop.common.errors import NotFoundError
from workshop.project.models import WorkshopProject
from workshop.proposal import service
from workshop.proposal.models import WorkshopProposalItem
from workshop.proposal.schemas import (
    ProposalItem,
    ProposalRound,
    ProposalRoundSummary,
    RoundComparison,
    RoundComparisonRow,
)
from workshop.review.schemas import Decision

router = APIRouter(tags=["Proposals"])


def _to_item(item: WorkshopProposalItem, decision: Any) -> ProposalItem:
    return ProposalItem(
        id=item.id,
        proposal_id=item.proposal_id,
        entity_type=EntityType(item.entity_type),
        entity_key=item.entity_key,
        proposed_value=item.proposed_value,
        explanation=item.explanation,
        confidence=item.confidence,
        is_assumption=item.is_assumption,
        has_conflict=item.has_conflict,
        conflict_alternatives=item.conflict_alternatives,
        source_refs=item.source_refs,
        likely_duplicate_of=item.likely_duplicate_of,
        carried_from_item_id=item.carried_from_item_id,
        state=service.state_for(decision),
        latest_decision=Decision.model_validate(decision) if decision is not None else None,
    )


def _round_counts(session: Session, proposal_id: uuid.UUID) -> dict[str, int]:
    items = service.items_for_proposal(session, proposal_id)
    decisions = service.decisions_for_items(session, [i.id for i in items])
    counts = {
        "total": len(items),
        "pending": 0,
        "accepted": 0,
        "rejected": 0,
        "modified": 0,
        "conflicts": 0,
        "assumptions": 0,
    }
    for item in items:
        state = service.state_for(decisions.get(item.id))
        counts[state.value.lower()] = counts.get(state.value.lower(), 0) + 1
        if item.has_conflict:
            counts["conflicts"] += 1
        if item.is_assumption:
            counts["assumptions"] += 1
    return counts


@router.get("/projects/{project_id}/proposals", response_model=list[ProposalRoundSummary])
def list_proposals(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[ProposalRoundSummary]:
    from sqlalchemy import select

    from workshop.proposal.models import WorkshopProposal

    proposals = session.execute(
        select(WorkshopProposal)
        .where(WorkshopProposal.project_id == project.id)
        .order_by(WorkshopProposal.round_number.desc())
    ).scalars()
    return [
        ProposalRoundSummary(
            id=p.id,
            project_id=p.project_id,
            round_number=p.round_number,
            created_at=p.created_at,
            item_counts=_round_counts(session, p.id),
        )
        for p in proposals
    ]


@router.get("/projects/{project_id}/proposals/{round_number}", response_model=ProposalRound)
def get_proposal_round(
    round_number: int,
    entity_type: EntityType | None = Query(default=None, alias="entityType"),
    item_state: ItemState | None = Query(default=None, alias="itemState"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> ProposalRound:
    proposal = service.proposal_by_round(session, project.id, round_number)
    if proposal is None:
        raise NotFoundError("Proposal round not found")

    items = service.items_for_proposal(session, proposal.id)
    decisions = service.decisions_for_items(session, [i.id for i in items])
    mapped = [_to_item(i, decisions.get(i.id)) for i in items]

    if entity_type is not None:
        mapped = [i for i in mapped if i.entity_type == entity_type]
    if item_state is not None:
        mapped = [i for i in mapped if i.state == item_state]

    total = len(mapped)
    start = (page - 1) * page_size
    page_items = mapped[start : start + page_size]

    return ProposalRound(
        id=proposal.id,
        project_id=proposal.project_id,
        round_number=proposal.round_number,
        created_at=proposal.created_at,
        items=page_items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/projects/{project_id}/proposals/{round_number}/compare",
    response_model=RoundComparison,
)
def compare_proposal_rounds(
    round_number: int,
    other_round_number: int = Query(alias="otherRoundNumber"),
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> RoundComparison:
    first = service.proposal_by_round(session, project.id, round_number)
    second = service.proposal_by_round(session, project.id, other_round_number)
    if first is None or second is None:
        raise NotFoundError("Proposal round not found")

    def index(proposal: Any) -> dict[str, WorkshopProposalItem]:
        return {i.entity_key: i for i in service.items_for_proposal(session, proposal.id)}

    first_items = index(first)
    second_items = index(second)
    keys = sorted(set(first_items) | set(second_items))
    rows: list[RoundComparisonRow] = []
    for key in keys:
        a = first_items.get(key)
        b = second_items.get(key)
        if a is not None and b is None:
            state, first_value, second_value = "Removed", a.proposed_value, None
        elif a is None and b is not None:
            state, first_value, second_value = "Added", None, b.proposed_value
        elif a is not None and b is not None and a.proposed_value != b.proposed_value:
            state, first_value, second_value = "Changed", a.proposed_value, b.proposed_value
        else:
            state = "Unchanged"
            first_value = a.proposed_value if a else None
            second_value = b.proposed_value if b else None
        rows.append(
            RoundComparisonRow(
                entity_type=EntityType((a or b).entity_type),  # type: ignore[union-attr]
                entity_key=key,
                state=state,
                first_value=first_value,
                second_value=second_value,
                first_confidence=(a.confidence if a else "Low"),
                second_confidence=(b.confidence if b else "Low"),
            )
        )

    return RoundComparison(
        project_id=project.id,
        round_number=round_number,
        other_round_number=other_round_number,
        rows=rows,
    )


@router.get(
    "/projects/{project_id}/proposal-items/{item_id}/trace",
    response_model=ProposalItem,
)
def trace_proposal_item(
    item_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> ProposalItem:
    item = session.get(WorkshopProposalItem, item_id)
    if item is None:
        raise NotFoundError("Proposal item not found")
    proposal = service.proposal_by_round(session, project.id, _round_for_item(session, item))
    if proposal is None or proposal.id != item.proposal_id:
        raise NotFoundError("Proposal item not found")
    decision = service.decisions_for_items(session, [item.id]).get(item.id)
    return _to_item(item, decision)


def _round_for_item(session: Session, item: WorkshopProposalItem) -> int:
    from workshop.proposal.models import WorkshopProposal

    proposal = session.get(WorkshopProposal, item.proposal_id)
    return proposal.round_number if proposal else -1
