"""Prompt templates: plain functions in source control, no prompt framework."""

from __future__ import annotations

from workshop.common.enums import EntityType
from workshop.parsing.models import ExtractedFact

SYSTEM_PROMPT = (
    "You normalize customer HR documents into an HRMS standard model. "
    "Return only well-formed structured output. Never invent values: when "
    "information is missing, set is_assumption=true and explain why. "
    "Cite the fact indexes you used. Never resolve conflicting values."
)


def extraction_prompt(
    entity_type: EntityType, facts: list[ExtractedFact], prior_accepted: list[dict[str, object]]
) -> str:
    lines = [f"Entity type: {entity_type.value}", "", "Extracted facts:"]
    for index, fact in enumerate(facts):
        lines.append(f"[{index}] {fact.text}")
    if prior_accepted:
        lines.append("")
        lines.append("Already accepted (do not change, use for consistency):")
        for item in prior_accepted:
            lines.append(f"- {item}")
    lines.append("")
    lines.append(
        "Propose one item per logical entity. Include entity_key, proposed_value, "
        "confidence (High/Medium/Low), is_assumption, explanation, source_fact_indexes."
    )
    return "\n".join(lines)


def mapping_prompt(entity_type: EntityType, entity_keys: list[str]) -> str:
    return (
        f"Normalize the following {entity_type.value} keys/terms to the HRMS standard "
        f"model. Suggest field-level mappings only where confident.\n" + "\n".join(f"- {key}" for key in entity_keys)
    )


def explain_prompt(entity_type: EntityType, proposed_value: dict[str, object]) -> str:
    return (
        f"Write a plain-language explanation for a non-technical HR reviewer of this "
        f"{entity_type.value} proposal: {proposed_value}"
    )
