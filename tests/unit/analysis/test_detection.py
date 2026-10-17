"""Unit tests: deterministic conflict and duplicate detection (T055)."""

from __future__ import annotations

from workshop.analysis.candidates import CandidateItem
from workshop.analysis.steps.detect_conflicts import detect_conflicts
from workshop.analysis.steps.detect_duplicates import detect_duplicates
from workshop.common.enums import Confidence, EntityType


def _item(key: str, name: str, entity_type: EntityType = EntityType.COMPANY) -> CandidateItem:
    return CandidateItem(
        entity_type=entity_type,
        entity_key=key,
        proposed_value={"name": name},
        explanation="e",
        confidence=Confidence.HIGH,
    )


def test_conflict_same_key_different_values_flagged_no_winner() -> None:
    items = [_item("Company:acme", "Acme Inc"), _item("Company:acme", "Acme Ltd")]
    result = detect_conflicts(items)
    assert len(result) == 1
    winner = result[0]
    assert winner.has_conflict is True
    assert winner.conflict_alternatives is not None
    assert len(winner.conflict_alternatives) == 2
    # The winner's value is untouched: no auto-resolution.
    assert winner.proposed_value in ({"name": "Acme Inc"}, {"name": "Acme Ltd"})


def test_same_key_identical_values_not_flagged() -> None:
    items = [_item("Company:acme", "Acme"), _item("Company:acme", "Acme")]
    result = detect_conflicts(items)
    assert len(result) == 1
    assert result[0].has_conflict is False


def test_duplicate_similar_names_flagged() -> None:
    items = [
        _item("Company:acme-corporation", "Acme"),
        _item("Company:acme-corporation-inc", "Acme"),
    ]
    result = detect_duplicates(items)
    assert result[0].likely_duplicate_of == result[1].entity_key


def test_dissimilar_names_not_flagged() -> None:
    items = [
        _item("Company:acme", "Acme"),
        _item("Company:globex", "Globex"),
    ]
    result = detect_duplicates(items)
    assert all(item.likely_duplicate_of is None for item in result)


def test_duplicates_are_entity_type_scoped() -> None:
    items = [
        _item("Company:acme-corporation", "Acme"),
        _item("Department:acme-corporation", "Acme", EntityType.DEPARTMENT),
    ]
    result = detect_duplicates(items)
    assert all(item.likely_duplicate_of is None for item in result)
