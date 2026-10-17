"""Validation rule interface and result type."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from workshop.common.enums import ValidationOutcome


@dataclass
class ValidationContext:
    project_id: uuid.UUID
    dataset: list[dict[str, Any]]
    unresolved_conflicts: list[dict[str, Any]] = field(default_factory=list)
    unacknowledged_assumptions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationRuleResult:
    rule_code: str
    result: ValidationOutcome
    failing_records: list[dict[str, Any]] = field(default_factory=list)


class ValidationRule(Protocol):
    code: str

    def evaluate(self, context: ValidationContext) -> ValidationRuleResult: ...
