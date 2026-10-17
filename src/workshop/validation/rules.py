"""The five validation rules. Plain classes, no rule engine."""

from __future__ import annotations

from typing import Any

from workshop.common.enums import EntityType, ValidationOutcome
from workshop.validation.base import ValidationContext, ValidationRuleResult

# Reference fields: entity type -> [(field, target entity type)]
_REFERENCE_FIELDS: dict[str, list[tuple[str, str]]] = {
    EntityType.LOCATION.value: [("company", EntityType.COMPANY.value)],
    EntityType.DEPARTMENT.value: [
        ("company", EntityType.COMPANY.value),
        ("parent", EntityType.DEPARTMENT.value),
    ],
    EntityType.COST_CENTER.value: [("company", EntityType.COMPANY.value)],
    EntityType.EMPLOYEE.value: [
        ("company", EntityType.COMPANY.value),
        ("department", EntityType.DEPARTMENT.value),
        ("location", EntityType.LOCATION.value),
        ("job_title", EntityType.JOB_TITLE.value),
    ],
    EntityType.REPORTING_LINE.value: [
        ("employee", EntityType.EMPLOYEE.value),
        ("manager", EntityType.EMPLOYEE.value),
    ],
}

_ORPHAN_REQUIRED: dict[str, list[str]] = {
    EntityType.LOCATION.value: ["company"],
    EntityType.DEPARTMENT.value: ["company"],
    EntityType.COST_CENTER.value: ["company"],
    EntityType.EMPLOYEE.value: ["company"],
}

_IDENTIFIER_FIELDS = ("identifier", "code", "id", "employee_id", "company_code")


def _identifiers(dataset: list[dict[str, Any]]) -> dict[str, set[str]]:
    by_type: dict[str, set[str]] = {}
    for row in dataset:
        for field_name in _IDENTIFIER_FIELDS:
            value = row["resulting_value"].get(field_name)
            if value not in (None, ""):
                by_type.setdefault(row["entity_type"], set()).add(str(value))
    return by_type


def _known_targets(dataset: list[dict[str, Any]], target_type: str) -> set[str]:
    targets: set[str] = set()
    for row in dataset:
        if row["entity_type"] != target_type:
            continue
        targets.add(row["entity_key"])
        name = row["resulting_value"].get("name")
        if name:
            targets.add(str(name))
        for field_name in _IDENTIFIER_FIELDS:
            value = row["resulting_value"].get(field_name)
            if value not in (None, ""):
                targets.add(str(value))
    return targets


class ReferentialIntegrityRule:
    code = "REFERENTIAL_INTEGRITY"

    def evaluate(self, context: ValidationContext) -> ValidationRuleResult:
        failing: list[dict[str, Any]] = []
        for row in context.dataset:
            references = _REFERENCE_FIELDS.get(row["entity_type"], [])
            for field_name, target_type in references:
                value = row["resulting_value"].get(field_name)
                if value in (None, ""):
                    continue
                targets = _known_targets(context.dataset, target_type)
                if str(value) not in targets:
                    failing.append(
                        {
                            "entity_type": row["entity_type"],
                            "entity_key": row["entity_key"],
                            "detail": f"'{field_name}' references missing {target_type}: {value}",
                        }
                    )
        return ValidationRuleResult(
            rule_code=self.code,
            result=ValidationOutcome.FAIL if failing else ValidationOutcome.PASS,
            failing_records=failing,
        )


class DuplicateIdentifierRule:
    code = "DUPLICATE_IDENTIFIER"

    def evaluate(self, context: ValidationContext) -> ValidationRuleResult:
        failing: list[dict[str, Any]] = []
        seen: dict[tuple[str, str], str] = {}
        for row in context.dataset:
            for field_name in _IDENTIFIER_FIELDS:
                value = row["resulting_value"].get(field_name)
                if value in (None, ""):
                    continue
                token = (row["entity_type"], str(value))
                if token in seen:
                    failing.append(
                        {
                            "entity_type": row["entity_type"],
                            "entity_key": row["entity_key"],
                            "detail": f"Duplicate {field_name} '{value}' also used by {seen[token]}",
                        }
                    )
                else:
                    seen[token] = row["entity_key"]
        return ValidationRuleResult(
            rule_code=self.code,
            result=ValidationOutcome.FAIL if failing else ValidationOutcome.PASS,
            failing_records=failing,
        )


class OrphanedEntityRule:
    code = "ORPHANED_ENTITY"

    def evaluate(self, context: ValidationContext) -> ValidationRuleResult:
        failing: list[dict[str, Any]] = []
        for row in context.dataset:
            for field_name in _ORPHAN_REQUIRED.get(row["entity_type"], []):
                if row["resulting_value"].get(field_name) in (None, ""):
                    failing.append(
                        {
                            "entity_type": row["entity_type"],
                            "entity_key": row["entity_key"],
                            "detail": f"Missing required parent reference '{field_name}'",
                        }
                    )
        return ValidationRuleResult(
            rule_code=self.code,
            result=ValidationOutcome.FAIL if failing else ValidationOutcome.PASS,
            failing_records=failing,
        )


class UnresolvedConflictRule:
    code = "UNRESOLVED_CONFLICT"

    def evaluate(self, context: ValidationContext) -> ValidationRuleResult:
        failing = [
            {
                "entity_type": row.get("entity_type", ""),
                "entity_key": row.get("entity_key", ""),
                "detail": "Conflict has no accepted or modified resolution",
            }
            for row in context.unresolved_conflicts
        ]
        return ValidationRuleResult(
            rule_code=self.code,
            result=ValidationOutcome.FAIL if failing else ValidationOutcome.PASS,
            failing_records=failing,
        )


class UnacknowledgedAssumptionRule:
    code = "UNACKNOWLEDGED_ASSUMPTION"

    def evaluate(self, context: ValidationContext) -> ValidationRuleResult:
        failing = [
            {
                "entity_type": row.get("entity_type", ""),
                "entity_key": row.get("entity_key", ""),
                "detail": "Assumption has not been acknowledged (accepted or modified)",
            }
            for row in context.unacknowledged_assumptions
        ]
        return ValidationRuleResult(
            rule_code=self.code,
            result=ValidationOutcome.FAIL if failing else ValidationOutcome.PASS,
            failing_records=failing,
        )
