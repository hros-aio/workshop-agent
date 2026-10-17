"""Extract-facts step: call the AIClient and build candidate items."""

from __future__ import annotations

from workshop.ai.client import AIClient
from workshop.ai.schemas import AIProposalItem
from workshop.analysis.candidates import CandidateItem
from workshop.common.enums import EntityType
from workshop.parsing.models import ExtractedFact


def extract_facts(
    ai: AIClient,
    *,
    entity_type: EntityType,
    facts: list[ExtractedFact],
    prior_accepted: list[dict[str, object]],
) -> list[CandidateItem]:
    response = ai.extract_facts(entity_type=entity_type, facts=facts, prior_accepted=prior_accepted)
    items: list[CandidateItem] = []
    for raw in response.items:
        # Re-validate so a provider that returns a wrong shape fails loudly.
        item = AIProposalItem.model_validate(raw)
        refs = [
            facts[index].source_ref.model_dump(mode="json")
            for index in item.source_fact_indexes
            if 0 <= index < len(facts)
        ]
        items.append(
            CandidateItem(
                entity_type=entity_type,
                entity_key=item.entity_key,
                proposed_value=item.proposed_value,
                explanation=item.explanation,
                confidence=item.confidence,
                is_assumption=item.is_assumption,
                source_refs=refs,
            )
        )
    return items
