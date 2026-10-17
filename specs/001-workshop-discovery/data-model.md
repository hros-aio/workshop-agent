# Phase 1 Data Model: Workshop Module

**Feature**: `001-workshop-discovery`
**Schema**: `workshop` (PostgreSQL) | **ORM**: SQLAlchemy 2.x | **Migrations**: Alembic (`version_table_schema="workshop"`)

All history-bearing tables are **append-only**. Rows shown with a "current" status are logical status fields on aggregate roots; the historical child rows (versions, decisions, rounds, results) are never updated or deleted. All tables carry `tenant_id` (or reach it via `project_id`) and every query is tenant-filtered.

---

## Enums

| Enum | Values |
|------|--------|
| `ProjectStatus` | `Setup`, `Collecting Documents`, `In Analysis`, `In Review`, `Finalized`, `Exported` |
| `DocumentStatus` | `Uploaded`, `Analyzed`, `Superseded`, `Parse Failed` |
| `AnalysisRunStatus` | `Queued`, `Running`, `Completed`, `Failed` |
| `DecisionAction` | `Accept`, `Reject`, `Modify` |
| `Confidence` | `High`, `Medium`, `Low` |
| `ValidationOutcome` | `Pass`, `Fail` |
| `EntityType` | `Company`, `Location`, `Department`, `CostCenter`, `JobTitle`, `Employee`, `ReportingLine`, `Role`, `ApprovalWorkflow` |
| `AIProvider` | `OPENAI`, `LOCAL_QWEN` |
| `ProjectRole` | `CONSULTANT`, `CUSTOMER_REVIEWER`, `PROJECT_MANAGER`, `ADMIN` |

---

## Aggregates and tables

### WorkshopProject (`workshop_project`)

The root aggregate; one row per engagement.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | UUID NOT NULL | from JWT; indexed |
| `customer_id` | UUID NOT NULL | platform customer reference |
| `name` | TEXT NOT NULL | |
| `status` | TEXT NOT NULL | `ProjectStatus`; default `Setup` |
| `ai_provider` | TEXT NOT NULL | `AIProvider`; `OPENAI` or `LOCAL_QWEN` |
| `scoped_entity_types` | TEXT[] NOT NULL | subset of `EntityType` |
| `current_round` | INT NOT NULL DEFAULT 0 | highest proposal round number |
| `responses_expect_no_value`… | — | (no extra columns; keep minimal) |
| `context_notes` | TEXT NULL | free-text consultant context (optional) |
| `reopen_count` | INT NOT NULL DEFAULT 0 | increments on each reopen |
| `created_by` | UUID NOT NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | status/config only; never historical rows |
| `archived_at` | TIMESTAMPTZ NULL | soft archive flag only; no deletes |

**Rules**: `scoped_entity_types` must be a non-empty subset of `EntityType` (may change only while `status = Setup`). `ai_provider` and scope may change only while `Setup`. `name` required, non-blank, ≤ 200 chars.

**Relationships**: 1—* `WorkshopProjectMember`, `WorkshopDocument`, `WorkshopAnalysisRun`, `WorkshopProposal`, `WorkshopValidationRun`, `WorkshopExportPackage`, `WorkshopAuditLog`.

### WorkshopProjectMember (`workshop_project_member`)

Project-scoped access on top of platform roles.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK → `workshop_project.id` | |
| `user_id` | UUID NOT NULL | platform user id |
| `role` | TEXT NOT NULL | `ProjectRole` |
| `added_by` | UUID NOT NULL | |
| `added_at` | TIMESTAMPTZ NOT NULL | |
| | | UNIQUE(`project_id`, `user_id`) |

**Rules**: A user may hold multiple roles on a project through multiple rows (unique is project+user+role; alternatively store a `roles TEXT[]` — chosen: **one row per (project, user, role)** to keep role checks simple and additive). At least one `CONSULTANT` or `ADMIN` must exist before a project can leave `Setup`.

### WorkshopDocument (`workshop_document`)

Logical document; version pointer moves forward.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK → `workshop_project.id` | |
| `document_type` | TEXT NOT NULL | tag chosen by uploader (e.g. `OrgChart`, `EmployeeList`, `Policy`, `LegacyExport`, `Other`) |
| `status` | TEXT NOT NULL | `DocumentStatus` |
| `current_version_id` | UUID FK → `workshop_document_version.id` NULL | |
| `notes` | TEXT NULL | |
| `created_by` | UUID NOT NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

**Rules**: Never deleted. Replacing moves `current_version_id` and sets the prior version `superseded_at`. `document_type` required.

### WorkshopDocumentVersion (`workshop_document_version`)

Insert-only file revision.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `document_id` | UUID FK → `workshop_document.id` | |
| `version_number` | INT NOT NULL | starts at 1; UNIQUE(`document_id`,`version_number`) |
| `storage_key` | TEXT NOT NULL | `workshop/{tenant}/{project}/documents/{doc}/{version}/{filename}` |
| `file_name` | TEXT NOT NULL | |
| `mime_type` | TEXT NOT NULL | |
| `size_bytes` | BIGINT NOT NULL | |
| `checksum_sha256` | TEXT NOT NULL | |
| `upload_status` | TEXT NOT NULL | `Pending`, `Uploaded`, `Failed` |
| `uploaded_by` | UUID NOT NULL | |
| `uploaded_at` | TIMESTAMPTZ NULL | set on completion |
| `superseded_at` | TIMESTAMPTZ NULL | set when a newer version becomes current |

**Rules**: Never updated except `upload_status`/`uploaded_at`/`superseded_at` lifecycle flags. Content changes always create a new row.

### WorkshopAnalysisRun (`workshop_analysis_run`)

One row per triggered run; captures the exact input snapshot.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK → `workshop_project.id` | |
| `round_number` | INT NOT NULL | target round for the resulting proposal |
| `status` | TEXT NOT NULL | `AnalysisRunStatus` |
| `ai_provider` | TEXT NOT NULL | resolved from project at trigger time |
| `document_version_ids` | UUID[] NOT NULL | input snapshot (active versions) |
| `prior_decision_ids` | UUID[] NULL | locked decisions used as context |
| `triggered_by` | UUID NOT NULL | |
| `started_at` | TIMESTAMPTZ NULL | |
| `completed_at` | TIMESTAMPTZ NULL | |
| `error_message` | TEXT NULL | populated on `Failed` |

**Rules**: A run in `Queued`/`Running` blocks a new run for the same project. On `Failed`, no proposal is written (FR-014).

### WorkshopProposal (`workshop_proposal`)

Immutable result of exactly one successful run.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK → `workshop_project.id` | |
| `analysis_run_id` | UUID FK → `workshop_analysis_run.id` UNIQUE | 1—1 |
| `round_number` | INT NOT NULL | UNIQUE(`project_id`,`round_number`) |
| `created_at` | TIMESTAMPTZ NOT NULL | |

### WorkshopProposalItem (`workshop_proposal_item`)

One proposed entity value.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `proposal_id` | UUID FK → `workshop_proposal.id` | |
| `entity_type` | TEXT NOT NULL | `EntityType` |
| `entity_key` | TEXT NOT NULL | deterministic, stable across rounds (R7) |
| `proposed_value` | JSONB NOT NULL | shape varies per entity type |
| `explanation` | TEXT NOT NULL | plain-language |
| `confidence` | TEXT NOT NULL | `Confidence` |
| `is_assumption` | BOOLEAN NOT NULL DEFAULT FALSE | |
| `has_conflict` | BOOLEAN NOT NULL DEFAULT FALSE | |
| `conflict_alternatives` | JSONB NULL | `[{ "value": {...}, "source_ref": {...} }]` |
| `source_refs` | JSONB NOT NULL | `[{ document_version_id, file_name, page|sheet, row, cell }]` |
| `likely_duplicate_of` | TEXT NULL | `entity_key` of a probable duplicate (R5) |
| `carried_from_item_id` | UUID FK → `workshop_proposal_item.id` NULL | set when locked & carried forward (FR-015) |
| `created_at` | TIMESTAMPTZ NOT NULL | |

Indexed on `(proposal_id)` and (via join) `(project_id, entity_key)`.

### WorkshopDecision (`workshop_decision`)

Immutable human action.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `proposal_item_id` | UUID FK → `workshop_proposal_item.id` | |
| `action` | TEXT NOT NULL | `DecisionAction` |
| `resulting_value` | JSONB NOT NULL | proposed value for Accept; edited value for Modify; proposed value echoed for Reject |
| `comment` | TEXT NULL | required for `Reject` and `Modify` |
| `decided_by` | UUID NOT NULL | |
| `decided_at` | TIMESTAMPTZ NOT NULL | |
| `reopened` | BOOLEAN NOT NULL DEFAULT FALSE | marks decisions invalidated by an explicit reopen |

**Rules**: Insert-only (FR-018). Application enforces comment for Reject/Modify (FR-017). Concurrent submissions create two rows; the read model surfaces the ambiguity rather than silently choosing (PRD §19).

### WorkshopValidationRun (`workshop_validation_run`) / WorkshopValidationResult (`workshop_validation_result`)

| `workshop_validation_run` | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK | |
| `round_number` | INT NOT NULL | dataset version validated |
| `triggered_by` | UUID NOT NULL | user or `system` |
| `triggered_at` | TIMESTAMPTZ NOT NULL | |
| `overall_result` | TEXT NOT NULL | `ValidationOutcome` |

| `workshop_validation_result` | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `validation_run_id` | UUID FK | |
| `rule_code` | TEXT NOT NULL | e.g. `REFERENTIAL_INTEGRITY`, `DUPLICATE_IDENTIFIER`, `ORPHANED_ENTITY`, `UNRESOLVED_CONFLICT`, `UNACKNOWLEDGED_ASSUMPTION` |
| `result` | TEXT NOT NULL | `ValidationOutcome` |
| `failing_records` | JSONB NULL | `[{ entity_type, entity_key, detail }]` |

**Rules**: A rule exception → `Fail` (conservative). Finalization requires the latest run's `overall_result = Pass` (FR-020, FR-023).

### WorkshopExportPackage (`workshop_export_package`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK | |
| `version_number` | INT NOT NULL | UNIQUE(`project_id`,`version_number`); starts at 1, increments on re-export after reopen |
| `storage_prefix` | TEXT NOT NULL | `workshop/{tenant}/{project}/exports/v{n}/` |
| `files` | JSONB NOT NULL | `[{ name, key, checksum }]` — the expected artifact set |
| `validation_run_id` | UUID FK | run whose `Pass` gated this export |
| `exported_by` | UUID NOT NULL | |
| `exported_at` | TIMESTAMPTZ NOT NULL | |

**In-scope artifacts**: one workbook per in-scope entity type — `Companies.xlsx`, `Locations.xlsx`, `Departments.xlsx`, `CostCenters.xlsx`, `JobTitles.xlsx`, `Employees.xlsx`, `ReportingLines.xlsx`, `Roles.xlsx`, `ApprovalWorkflows.xlsx` — plus `DifferenceReport.xlsx`, `ValidationReport.xlsx`, `DecisionLog.xlsx`.

### WorkshopAuditLog (`workshop_audit_log`)

Append-only business audit trail.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID NULL | |
| `tenant_id` | UUID NOT NULL | |
| `actor_id` | UUID NULL | `system` for automated steps |
| `action` | TEXT NOT NULL | e.g. `PROJECT_CREATED`, `DOCUMENT_UPLOADED`, `DOCUMENT_SUPERSEDED`, `ANALYSIS_TRIGGERED`, `ANALYSIS_COMPLETED`, `ANALYSIS_FAILED`, `PROPOSAL_GENERATED`, `DECISION_RECORDED`, `VALIDATION_RUN`, `STATUS_TRANSITION`, `PROJECT_FINALIZED`, `EXPORT_GENERATED`, `PROJECT_REOPENED`, `MEMBER_ADDED` |
| `entity_type` | TEXT NULL | |
| `entity_id` | UUID NULL | |
| `payload` | JSONB NOT NULL | action-specific detail |
| `occurred_at` | TIMESTAMPTZ NOT NULL | |

**Rules**: Insert-only; never reconstructed into current state (state lives in the aggregate tables).

---

## Relationships

```
WorkshopProject 1───* WorkshopProjectMember
WorkshopProject 1───* WorkshopDocument 1───* WorkshopDocumentVersion
WorkshopProject 1───* WorkshopAnalysisRun 1───1 WorkshopProposal 1───* WorkshopProposalItem
                                                                            │
                                                                           1│*
                                                                  WorkshopDecision
WorkshopProject 1───* WorkshopValidationRun 1───* WorkshopValidationResult
WorkshopProject 1───* WorkshopExportPackage
WorkshopProject 1───* WorkshopAuditLog
```

---

## Lifecycle state machine

`ALLOWED_TRANSITIONS` (constitution V: enum + guard functions, no engine):

| From | Allowed to |
|------|-----------|
| `Setup` | `Collecting Documents` |
| `Collecting Documents` | `In Analysis` |
| `In Analysis` | `In Review` |
| `In Review` | `In Analysis`, `Finalized` |
| `Finalized` | `Exported` |
| `Exported` | `In Review` (explicit reopen only) |

**Guards**:

- `Setup → Collecting Documents`: scope non-empty; at least one member.
- `Collecting Documents → In Analysis`: triggered by the Analysis Run trigger itself (run inserted first, then transition).
- `In Analysis → In Review`: only the worker on a successful run.
- `In Review → In Analysis`: a new Analysis Run is triggered (round = `current_round + 1`).
- `In Review → Finalized`: every item is resolved (has an `Accept`/`Modify` decision; no pending or rejected item remains) **and** latest `WorkshopValidationRun.overall_result = Pass`.
- `Finalized → Exported`: export completed all-or-nothing.
- `Exported → In Review`: explicit reopen; writes `PROJECT_REOPENED` audit event and increments `reopen_count`.

Every transition writes a `STATUS_TRANSITION` audit event.

---

## Derived read model: current accepted dataset

Not a table. Computed on demand (R6), used by Validation and Export:

```sql
SELECT DISTINCT ON (pi.entity_key)
       pi.entity_key,
       pi.entity_type,
       d.resulting_value,
       d.decided_by,
       d.decided_at,
       pi.source_refs,
       pi.is_assumption
FROM workshop.workshop_proposal_item pi
JOIN workshop.workshop_decision d ON d.proposal_item_id = pi.id
JOIN workshop.workshop_proposal p ON p.id = pi.proposal_id
WHERE p.project_id = :project_id
  AND d.action IN ('Accept', 'Modify')
  AND d.reopened = FALSE
ORDER BY pi.entity_key, p.round_number DESC, d.decided_at DESC;
```

**Item-resolution rule** (used by the finalization guard): an item is resolved when the latest decision for its `entity_key` is `Accept` or `Modify`. A `Reject` leaves the key unresolved and it must appear in the next round.

---

## Mapping to requirements

| Requirement group | Tables |
|-------------------|--------|
| FR-001–FR-004 project/scope/membership | `workshop_project`, `workshop_project_member` |
| FR-005–FR-008 documents/versions/snapshot | `workshop_document`, `workshop_document_version`, `workshop_analysis_run.document_version_ids` |
| FR-009–FR-016 analysis/proposals | `workshop_analysis_run`, `workshop_proposal`, `workshop_proposal_item` |
| FR-017–FR-018 review/decisions | `workshop_decision` |
| FR-019–FR-021 lifecycle | `workshop_project.status`, `reopen_count`, audit log |
| FR-022–FR-023 validation | `workshop_validation_run`, `workshop_validation_result` |
| FR-024–FR-026 export | `workshop_export_package` |
| FR-027–FR-028 traceability/audit | `source_refs`, `workshop_decision`, `workshop_audit_log` |
| FR-029–FR-030 provider independence | `workshop_project.ai_provider`, `workshop_analysis_run.ai_provider` |
