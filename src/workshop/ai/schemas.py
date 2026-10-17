"""Structured-output schemas for every AI call.

These schemas are validated against every provider response. Invalid output
raises and fails the Analysis Run; it never becomes a proposal item.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from workshop.common.enums import Confidence


class AIProposalItem(BaseModel):
    entity_key: str = Field(min_length=1)
    proposed_value: dict[str, Any]
    confidence: Confidence
    is_assumption: bool = False
    explanation: str = Field(min_length=1)
    # Indexes into the facts list supplied to this call; the orchestrator maps
    # them to concrete SourceRefs so traceability stays deterministic.
    source_fact_indexes: list[int] = Field(default_factory=list)


class ExtractFactsResponse(BaseModel):
    items: list[AIProposalItem] = Field(default_factory=list)


class MappingSuggestion(BaseModel):
    entity_key: str
    field: str
    from_value: str
    to_value: str
    explanation: str
    confidence: Confidence


class MappingResponse(BaseModel):
    suggestions: list[MappingSuggestion] = Field(default_factory=list)


class ExplainResponse(BaseModel):
    explanation: str = Field(min_length=1)
