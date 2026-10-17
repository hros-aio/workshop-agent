"""Deterministic conflict detection: same entity, different values. No winner."""

from __future__ import annotations

from workshop.analysis.candidates import CandidateItem


def _first_ref(item: CandidateItem) -> dict[str, object]:
    return item.source_refs[0] if item.source_refs else {}


def detect_conflicts(items: list[CandidateItem]) -> list[CandidateItem]:
    grouped: dict[tuple[str, str], list[CandidateItem]] = {}
    for item in items:
        grouped.setdefault((item.entity_type.value, item.entity_key), []).append(item)

    result: list[CandidateItem] = []
    for group in grouped.values():
        distinct_values = {_freeze(item.proposed_value): item for item in group}
        if len(distinct_values) <= 1:
            result.append(group[0])
            continue

        base = group[0]
        alternatives = [{"value": item.proposed_value, "source_ref": _first_ref(item)} for item in group]
        base.has_conflict = True
        base.conflict_alternatives = alternatives
        result.append(base)
    return result


def _freeze(value: dict[str, object]) -> str:
    return repr(sorted((str(k), str(v)) for k, v in value.items()))
