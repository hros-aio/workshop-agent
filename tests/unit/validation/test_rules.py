"""Unit tests: each validation rule in isolation (T082)."""

from __future__ import annotations

import uuid

from workshop.common.enums import EntityType, ValidationOutcome
from workshop.validation.base import ValidationContext
from workshop.validation.registry import get_rules
from workshop.validation.rules import (
    DuplicateIdentifierRule,
    OrphanedEntityRule,
    ReferentialIntegrityRule,
    UnacknowledgedAssumptionRule,
    UnresolvedConflictRule,
)


def _row(entity_type: EntityType, key: str, value: dict[str, object]) -> dict[str, object]:
    return {"entity_type": entity_type.value, "entity_key": key, "resulting_value": value}


def _context(
    dataset: list[dict[str, object]],
    *,
    unresolved_conflicts: list[dict[str, object]] | None = None,
    unacknowledged_assumptions: list[dict[str, object]] | None = None,
) -> ValidationContext:
    return ValidationContext(
        project_id=uuid.uuid4(),
        dataset=dataset,
        unresolved_conflicts=unresolved_conflicts or [],
        unacknowledged_assumptions=unacknowledged_assumptions or [],
    )


def test_referential_integrity_passes_when_targets_exist() -> None:
    ctx = _context(
        [
            _row(EntityType.COMPANY, "Company:acme", {"name": "Acme", "code": "ACME"}),
            _row(EntityType.EMPLOYEE, "Employee:jane", {"first_name": "Jane", "company": "ACME"}),
        ]
    )
    assert ReferentialIntegrityRule().evaluate(ctx).result == ValidationOutcome.PASS


def test_referential_integrity_fails_for_dangling_reference() -> None:
    ctx = _context([_row(EntityType.EMPLOYEE, "Employee:jane", {"first_name": "Jane", "company": "MISSING"})])
    result = ReferentialIntegrityRule().evaluate(ctx)
    assert result.result == ValidationOutcome.FAIL
    assert result.failing_records


def test_duplicate_identifier_detected() -> None:
    ctx = _context(
        [
            _row(EntityType.COMPANY, "Company:a", {"code": "DUP"}),
            _row(EntityType.COMPANY, "Company:b", {"code": "DUP"}),
        ]
    )
    result = DuplicateIdentifierRule().evaluate(ctx)
    assert result.result == ValidationOutcome.FAIL


def test_orphaned_entity_requires_parent() -> None:
    ctx = _context([_row(EntityType.DEPARTMENT, "Department:hr", {"name": "HR"})])
    result = OrphanedEntityRule().evaluate(ctx)
    assert result.result == ValidationOutcome.FAIL


def test_unresolved_conflict_fails() -> None:
    ctx = _context([], unresolved_conflicts=[{"entity_type": "Company", "entity_key": "c"}])
    assert UnresolvedConflictRule().evaluate(ctx).result == ValidationOutcome.FAIL


def test_unacknowledged_assumption_fails() -> None:
    ctx = _context([], unacknowledged_assumptions=[{"entity_key": "c"}])
    assert UnacknowledgedAssumptionRule().evaluate(ctx).result == ValidationOutcome.FAIL


def test_clean_context_passes_all_rules() -> None:
    ctx = _context([_row(EntityType.COMPANY, "Company:acme", {"name": "Acme", "code": "ACME"})])
    results = [rule.evaluate(ctx) for rule in get_rules()]
    assert all(r.result == ValidationOutcome.PASS for r in results)
