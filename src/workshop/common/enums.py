"""Shared domain enums. Values must match data-model.md exactly."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    SETUP = "Setup"
    COLLECTING_DOCUMENTS = "Collecting Documents"
    IN_ANALYSIS = "In Analysis"
    IN_REVIEW = "In Review"
    FINALIZED = "Finalized"
    EXPORTED = "Exported"


class DocumentStatus(StrEnum):
    UPLOADED = "Uploaded"
    ANALYZED = "Analyzed"
    SUPERSEDED = "Superseded"
    PARSE_FAILED = "Parse Failed"


class UploadStatus(StrEnum):
    PENDING = "Pending"
    UPLOADED = "Uploaded"
    FAILED = "Failed"


class AnalysisRunStatus(StrEnum):
    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class DecisionAction(StrEnum):
    ACCEPT = "Accept"
    REJECT = "Reject"
    MODIFY = "Modify"


class Confidence(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ValidationOutcome(StrEnum):
    PASS = "Pass"
    FAIL = "Fail"


class EntityType(StrEnum):
    COMPANY = "Company"
    LOCATION = "Location"
    DEPARTMENT = "Department"
    COST_CENTER = "CostCenter"
    JOB_TITLE = "JobTitle"
    EMPLOYEE = "Employee"
    REPORTING_LINE = "ReportingLine"
    ROLE = "Role"
    APPROVAL_WORKFLOW = "ApprovalWorkflow"


class AIProvider(StrEnum):
    OPENAI = "OPENAI"
    LOCAL_QWEN = "LOCAL_QWEN"


class ProjectRole(StrEnum):
    CONSULTANT = "CONSULTANT"
    CUSTOMER_REVIEWER = "CUSTOMER_REVIEWER"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    ADMIN = "ADMIN"


class ItemState(StrEnum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    MODIFIED = "Modified"


class AuditAction(StrEnum):
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_SUPERSEDED = "DOCUMENT_SUPERSEDED"
    DOCUMENT_PARSE_FAILED = "DOCUMENT_PARSE_FAILED"
    ANALYSIS_TRIGGERED = "ANALYSIS_TRIGGERED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    PROPOSAL_GENERATED = "PROPOSAL_GENERATED"
    DECISION_RECORDED = "DECISION_RECORDED"
    VALIDATION_RUN = "VALIDATION_RUN"
    STATUS_TRANSITION = "STATUS_TRANSITION"
    PROJECT_FINALIZED = "PROJECT_FINALIZED"
    EXPORT_GENERATED = "EXPORT_GENERATED"
    PROJECT_REOPENED = "PROJECT_REOPENED"


# Roles permitted to perform each action (platform RBAC is separate; this is
# the project-scoped layer enforced by require_project_role).
PROJECT_CONFIG_ROLES = (ProjectRole.CONSULTANT, ProjectRole.ADMIN)
UPLOAD_ROLES = (ProjectRole.CONSULTANT, ProjectRole.CUSTOMER_REVIEWER, ProjectRole.ADMIN)
TRIGGER_ANALYSIS_ROLES = (ProjectRole.CONSULTANT, ProjectRole.ADMIN)
REVIEW_ROLES = (ProjectRole.CONSULTANT, ProjectRole.CUSTOMER_REVIEWER, ProjectRole.ADMIN)
VIEW_ROLES = (
    ProjectRole.CONSULTANT,
    ProjectRole.CUSTOMER_REVIEWER,
    ProjectRole.PROJECT_MANAGER,
    ProjectRole.ADMIN,
)
FINALIZE_ROLES = (ProjectRole.CONSULTANT, ProjectRole.ADMIN)
EXPORT_ROLES = (ProjectRole.CONSULTANT, ProjectRole.ADMIN)
REOPEN_ROLES = (ProjectRole.CONSULTANT, ProjectRole.ADMIN)
