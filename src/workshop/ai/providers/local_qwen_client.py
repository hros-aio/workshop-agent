"""Local Qwen provider adapter (self-hosted vLLM OpenAI-compatible endpoint).

Provides identical behavior to the OpenAI adapter; only base_url and credentials
differ. Local Qwen is preferred by customers with data-residency requirements.
"""

from __future__ import annotations

from workshop.ai import prompts
from workshop.ai.client import AIClient
from workshop.ai.providers.base import OpenAICompatibleClient
from workshop.ai.schemas import ExplainResponse, ExtractFactsResponse, MappingResponse
from workshop.common.enums import EntityType
from workshop.parsing.models import ExtractedFact
from workshop.settings import get_settings


class LocalQwenClient(AIClient, OpenAICompatibleClient):
    def __init__(self) -> None:
        settings = get_settings()
        OpenAICompatibleClient.__init__(
            self,
            model=settings.qwen_model,
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )

    def extract_facts(
        self,
        *,
        entity_type: EntityType,
        facts: list[ExtractedFact],
        prior_accepted: list[dict[str, object]],
    ) -> ExtractFactsResponse:
        return self._complete(
            response_model=ExtractFactsResponse,
            system=prompts.SYSTEM_PROMPT,
            user=prompts.extraction_prompt(entity_type, facts, prior_accepted),
        )

    def recommend_mapping(self, *, entity_type: EntityType, entity_keys: list[str]) -> MappingResponse:
        return self._complete(
            response_model=MappingResponse,
            system=prompts.SYSTEM_PROMPT,
            user=prompts.mapping_prompt(entity_type, entity_keys),
        )

    def explain(self, *, entity_type: EntityType, proposed_value: dict[str, object]) -> str:
        response = self._complete(
            response_model=ExplainResponse,
            system=prompts.SYSTEM_PROMPT,
            user=prompts.explain_prompt(entity_type, proposed_value),
        )
        return response.explanation
