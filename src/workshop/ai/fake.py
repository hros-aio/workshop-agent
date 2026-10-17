"""Deterministic fake AIClient for tests and the full flow without a real model."""

from __future__ import annotations

import re

from workshop.ai.client import AIClient
from workshop.ai.schemas import AIProposalItem, ExtractFactsResponse, MappingResponse
from workshop.common.enums import Confidence, EntityType
from workshop.parsing.models import ExtractedFact

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG.sub("-", value.lower()).strip("-")[:80] or "unknown"


class AIFailure(Exception):
    """Raised by the fake to simulate provider failure."""


class FakeAIClient(AIClient):
    """Deterministic, schema-valid output. Set `fail=True` to simulate a failure
    and `invalid=True` to simulate schema-invalid output."""

    def __init__(self, *, fail: bool = False, invalid: bool = False) -> None:
        self.fail = fail
        self.invalid = invalid

    def extract_facts(
        self,
        *,
        entity_type: EntityType,
        facts: list[ExtractedFact],
        prior_accepted: list[dict[str, object]],
    ) -> ExtractFactsResponse:
        if self.fail:
            raise AIFailure("simulated provider failure")
        if self.invalid:
            # Bypass validation: return an object missing required fields so the
            # caller's re-validation fails loudly.
            from typing import Any, cast

            return ExtractFactsResponse.model_construct(items=cast(Any, [{"entity_key": "x"}]))

        accepted_keys = {str(item.get("entity_key")) for item in prior_accepted}
        items: list[AIProposalItem] = []
        for index, fact in enumerate(facts):
            key = f"{entity_type.value}:{_slug(fact.text)}"
            if key in accepted_keys:
                continue
            confidence = Confidence.HIGH
            if fact.ocr_confidence is not None and fact.ocr_confidence < 0.6:
                confidence = Confidence.LOW
            items.append(
                AIProposalItem(
                    entity_key=key,
                    proposed_value={"name": fact.text},
                    confidence=confidence,
                    is_assumption=False,
                    explanation=f"Derived from {fact.source_ref.file_name}.",
                    source_fact_indexes=[index],
                )
            )
        return ExtractFactsResponse(items=items)

    def recommend_mapping(self, *, entity_type: EntityType, entity_keys: list[str]) -> MappingResponse:
        if self.fail:
            raise AIFailure("simulated provider failure")
        return MappingResponse(suggestions=[])

    def explain(self, *, entity_type: EntityType, proposed_value: dict[str, object]) -> str:
        if self.fail:
            raise AIFailure("simulated provider failure")
        return f"Proposed {entity_type.value} based on the referenced source documents."
