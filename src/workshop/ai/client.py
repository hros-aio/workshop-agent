"""The provider-agnostic AIClient interface.

The analysis orchestrator depends only on this Protocol. Each provider adapter
builds the provider-specific request, calls the endpoint, and maps the raw
response into these shared types, validating against the schemas in
`workshop.ai.schemas`. Provider choice must not affect analysis behavior.
"""

from __future__ import annotations

from typing import Protocol

from workshop.ai.schemas import ExtractFactsResponse, MappingResponse
from workshop.common.enums import EntityType
from workshop.parsing.models import ExtractedFact


class PriorAcceptedItem(Protocol):
    entity_key: str
    entity_type: str
    proposed_value: dict[str, object]


class AIClient(Protocol):
    def extract_facts(
        self,
        *,
        entity_type: EntityType,
        facts: list[ExtractedFact],
        prior_accepted: list[dict[str, object]],
    ) -> ExtractFactsResponse: ...

    def recommend_mapping(
        self,
        *,
        entity_type: EntityType,
        entity_keys: list[str],
    ) -> MappingResponse: ...

    def explain(self, *, entity_type: EntityType, proposed_value: dict[str, object]) -> str: ...
