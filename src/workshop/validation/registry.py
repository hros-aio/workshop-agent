"""Validation rule registry: adding a rule = one class + one entry."""

from __future__ import annotations

from workshop.validation.base import ValidationRule
from workshop.validation.rules import (
    DuplicateIdentifierRule,
    OrphanedEntityRule,
    ReferentialIntegrityRule,
    UnacknowledgedAssumptionRule,
    UnresolvedConflictRule,
)


def get_rules() -> list[ValidationRule]:
    return [
        ReferentialIntegrityRule(),
        DuplicateIdentifierRule(),
        OrphanedEntityRule(),
        UnresolvedConflictRule(),
        UnacknowledgedAssumptionRule(),
    ]
