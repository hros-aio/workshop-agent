"""Deterministic duplicate detection (rapidfuzz). AI is not involved."""

from __future__ import annotations

from rapidfuzz import fuzz

from workshop.analysis.candidates import CandidateItem
from workshop.settings import get_settings


def detect_duplicates(items: list[CandidateItem]) -> list[CandidateItem]:
    threshold = get_settings().duplicate_similarity_threshold
    for index, item in enumerate(items):
        best_score = 0.0
        best_key: str | None = None
        for other_index, other in enumerate(items):
            if index == other_index or other.entity_type != item.entity_type:
                continue
            if other.entity_key == item.entity_key:
                continue
            score = fuzz.token_set_ratio(item.entity_key, other.entity_key)
            if score > best_score:
                best_score = score
                best_key = other.entity_key
        if best_key is not None and best_score >= threshold:
            item.likely_duplicate_of = best_key
    return items
