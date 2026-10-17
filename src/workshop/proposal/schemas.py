"""Proposal request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from workshop.common.enums import Confidence, EntityType, ItemState
from workshop.common.types import Schema
from workshop.parsing.models import SourceRef
from workshop.review.schemas import Decision


class ConflictAlternative(BaseModel):
    value: dict[str, Any]
    source_ref: dict[str, Any]


class ProposalItem(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    entity_type: EntityType
    entity_key: str
    proposed_value: dict[str, Any]
    explanation: str
    confidence: Confidence
    is_assumption: bool
    has_conflict: bool
    conflict_alternatives: list[ConflictAlternative] | None = None
    source_refs: list[SourceRef]
    likely_duplicate_of: str | None = None
    carried_from_item_id: uuid.UUID | None = None
    state: ItemState
    latest_decision: Decision | None = None


class ProposalRoundSummary(Schema):
    id: uuid.UUID
    project_id: uuid.UUID
    round_number: int
    created_at: datetime
    item_counts: dict[str, int]


class ProposalRound(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    round_number: int
    created_at: datetime
    items: list[ProposalItem]
    page: int
    page_size: int
    total: int


class RoundComparisonRow(BaseModel):
    entity_type: EntityType
    entity_key: str
    state: str
    first_value: dict[str, Any] | None = None
    second_value: dict[str, Any] | None = None
    first_confidence: Confidence
    second_confidence: Confidence


class RoundComparison(BaseModel):
    project_id: uuid.UUID
    round_number: int
    other_round_number: int
    rows: list[RoundComparisonRow]
