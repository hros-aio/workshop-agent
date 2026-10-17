"""Recommend-mapping step: semantic normalization via the AIClient.

The analysis module depends only on the AIClient interface here.
"""

from __future__ import annotations

from workshop.ai.client import AIClient
from workshop.ai.schemas import MappingSuggestion
from workshop.analysis.candidates import CandidateItem
from workshop.common.enums import EntityType


def recommend_mapping(ai: AIClient, *, entity_type: EntityType, items: list[CandidateItem]) -> list[MappingSuggestion]:
    keys = [item.entity_key for item in items]
    if not keys:
        return []
    response = ai.recommend_mapping(entity_type=entity_type, entity_keys=keys)
    return list(response.suggestions)
