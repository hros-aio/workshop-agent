"""HRMS standard import template definitions.

Each in-scope entity type maps to a workbook filename and an ordered list of
`(header, field)` columns. Field names are the canonical keys used inside a
proposal item's `proposed_value`. Provenance columns are appended by the
generator, not declared here.
"""

from __future__ import annotations

from dataclasses import dataclass

from workshop.common.enums import EntityType


@dataclass(frozen=True)
class TemplateSpec:
    file_name: str
    columns: tuple[tuple[str, str], ...]


ENTITY_TEMPLATES: dict[str, TemplateSpec] = {
    EntityType.COMPANY.value: TemplateSpec(
        "Companies.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Legal Name", "legal_name"),
            ("Country", "country"),
            ("Registration Number", "registration_number"),
            ("Parent Company", "parent_company"),
        ),
    ),
    EntityType.LOCATION.value: TemplateSpec(
        "Locations.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Company Code", "company"),
            ("Address Line 1", "address_line_1"),
            ("City", "city"),
            ("Country", "country"),
            ("Time Zone", "time_zone"),
        ),
    ),
    EntityType.DEPARTMENT.value: TemplateSpec(
        "Departments.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Company Code", "company"),
            ("Parent Department", "parent"),
            ("Cost Center Code", "cost_center"),
            ("Manager Employee Id", "manager"),
        ),
    ),
    EntityType.COST_CENTER.value: TemplateSpec(
        "CostCenters.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Company Code", "company"),
            ("Description", "description"),
        ),
    ),
    EntityType.JOB_TITLE.value: TemplateSpec(
        "JobTitles.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Job Family", "job_family"),
            ("Grade", "grade"),
            ("Description", "description"),
        ),
    ),
    EntityType.EMPLOYEE.value: TemplateSpec(
        "Employees.xlsx",
        (
            ("Employee Id", "employee_id"),
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Email", "email"),
            ("Company Code", "company"),
            ("Department Code", "department"),
            ("Location Code", "location"),
            ("Job Title Code", "job_title"),
            ("Manager Employee Id", "manager"),
            ("Hire Date", "hire_date"),
            ("Employment Type", "employment_type"),
        ),
    ),
    EntityType.REPORTING_LINE.value: TemplateSpec(
        "ReportingLines.xlsx",
        (
            ("Employee Id", "employee"),
            ("Manager Employee Id", "manager"),
            ("Relationship Type", "relationship_type"),
        ),
    ),
    EntityType.ROLE.value: TemplateSpec(
        "Roles.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Description", "description"),
            ("Permission Scope", "permission_scope"),
        ),
    ),
    EntityType.APPROVAL_WORKFLOW.value: TemplateSpec(
        "ApprovalWorkflows.xlsx",
        (
            ("Code", "code"),
            ("Name", "name"),
            ("Entity Type", "entity_type"),
            ("Approver Role", "approver_role"),
            ("Threshold", "threshold"),
            ("Sequence", "sequence"),
        ),
    ),
}

PROVENANCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Source Document", "_source_document"),
    ("Source Reference", "_source_reference"),
    ("Approved By", "_approved_by"),
)

DIFFERENCE_REPORT_FILE = "DifferenceReport.xlsx"
VALIDATION_REPORT_FILE = "ValidationReport.xlsx"
DECISION_LOG_FILE = "DecisionLog.xlsx"


def template_for(entity_type: str) -> TemplateSpec:
    return ENTITY_TEMPLATES[entity_type]


def file_names_for(scoped_entity_types: list[str]) -> list[str]:
    return [ENTITY_TEMPLATES[t].file_name for t in scoped_entity_types if t in ENTITY_TEMPLATES]
