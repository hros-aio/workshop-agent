"""Unit tests: AI structured-output schema validation (T054)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from workshop.ai.schemas import AIProposalItem, Confidence, ExtractFactsResponse


def test_valid_item_accepted() -> None:
    item = AIProposalItem(
        entity_key="Company:acme",
        proposed_value={"name": "Acme"},
        confidence=Confidence.HIGH,
        explanation="From intake form",
        source_fact_indexes=[0],
    )
    assert item.entity_key == "Company:acme"


@pytest.mark.parametrize(
    "payload",
    [
        {"entity_key": "x"},  # missing required fields
        {"entity_key": "", "proposed_value": {}, "confidence": "High", "explanation": "e"},
        {
            "entity_key": "x",
            "proposed_value": {},
            "confidence": "Nonsense",
            "explanation": "e",
        },
        {
            "entity_key": "x",
            "proposed_value": {},
            "confidence": "High",
            "explanation": "",
        },
    ],
)
def test_malformed_item_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AIProposalItem.model_validate(payload)


def test_response_requires_item_shapes() -> None:
    with pytest.raises(ValidationError):
        ExtractFactsResponse.model_validate({"items": [{"entity_key": "x"}]})
    ok = ExtractFactsResponse.model_validate({"items": []})
    assert ok.items == []
