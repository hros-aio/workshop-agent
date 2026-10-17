# Feature Specification: Workshop Module — AI-Assisted Discovery Workflow

**Feature Branch**: `001-workshop-discovery`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: "Build the Workshop Module for an HRMS SaaS platform: an AI-assisted discovery workflow that reduces customer implementation workshops from many meetings to 2-3 review rounds."

## Overview

During an HRMS implementation, consultants currently gather customer documents (org charts, employee lists, legacy exports, policies), manually translate the customer's terminology into the HRMS standard model, and iterate with the customer over many meetings until both sides agree. This is slow, inconsistent, and leaves no audit trail.

The Workshop Module replaces that manual process with a single structured discovery workflow: documents are collected and versioned, a deterministic-plus-AI analysis proposes a normalized model with explanations and evidence, users review proposals in a small number of rounds, and a validated, versioned implementation package is exported for the HRMS import tool. The module never writes to production HRMS data and never performs the import itself.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a Workshop Project and define scope (Priority: P1)

An Implementation Consultant creates a Workshop Project for a customer and selects which entity types are in scope: Companies, Locations, Departments, Cost Centers, Job Titles, Employees, Reporting Lines, Roles, Approval Workflows.

**Why this priority**: Everything else in the workflow is scoped to a project; without this no value can be delivered.

**Independent Test**: A consultant can create a project, choose a subset of entity types, see it saved with status "Setup", and move it to "Collecting Documents".

**Acceptance Scenarios**:

1. **Given** a consultant with project-creation permission, **When** they create a project for a customer and select entity types, **Then** the project is created with lifecycle status `Setup` and records the selected entity types and the chosen AI provider.
2. **Given** a project in `Setup`, **When** the consultant confirms scope, **Then** the project transitions to `Collecting Documents` and only the selected entity types are collected, analyzed, proposed, validated, and exported.
3. **Given** a user without project-creation permission, **When** they attempt to create or configure a project, **Then** the action is denied and no project is created.

---

### User Story 2 - Collect, version, and tag source documents (Priority: P1)

The Consultant and the Customer HR/Business Owner upload source documents (PDF, Word, Excel, CSV, scanned images) and tag each with a document type. Replacing a document creates a new version and marks the prior version `Superseded`; nothing is ever deleted.

**Why this priority**: Proposals and traceability depend entirely on a trustworthy, versioned evidence base.

**Independent Test**: Upload two versions of the same document with different content, confirm the older version is retained as `Superseded`, and confirm analysis uses only the active version.

**Acceptance Scenarios**:

1. **Given** a project in `Collecting Documents`, **When** a permitted user uploads a document and tags its type, **Then** the document is stored with an `Uploaded` status and a version number, attributed to the uploader and timestamp.
2. **Given** an existing document, **When** a permitted user replaces it, **Then** a new version is created, the previous version is marked `Superseded`, and the previous version remains retrievable.
3. **Given** a document tagged for an entity type not in the project scope, **When** analysis runs, **Then** that document is not used for that entity type.
4. **Given** an uploaded file in an unsupported or corrupt format, **When** the user uploads it, **Then** the upload is rejected with a clear message and the project state is unchanged.

---

### User Story 3 - Trigger an analysis run that produces a proposal round (Priority: P1)

The Consultant triggers an Analysis Run. The system extracts business facts from the active documents, detects conflicts between documents, detects likely duplicates, recommends mappings to the HRMS standard model, and recommends organization structure, reporting lines, approval structures, and department/job-title normalization. Each recommendation carries a plain-language explanation, a confidence level, source references, and an explicit Assumption flag when information is missing. Conflicts are never resolved by the system.

**Why this priority**: This is the core value — turning raw documents into an explained, evidence-backed draft model.

**Independent Test**: With a fixed set of sample documents, trigger an analysis run and confirm it produces a numbered proposal round of items, each with explanation, confidence, source references, and conflict/assumption flags.

**Acceptance Scenarios**:

1. **Given** a project in `Collecting Documents` with at least one active document, **When** the consultant triggers an analysis run, **Then** the project enters `In Analysis` and, on success, a new numbered Proposal Round is created with Proposal Items in `Pending` state.
2. **Given** two documents that state different values for the same logical entity, **When** analysis runs, **Then** the resulting item is flagged as a conflict and shows every alternative with its source, and the system selects no winner.
3. **Given** an item whose value was inferred rather than stated in a document, **When** the item is produced, **Then** it carries an explicit Assumption flag and is not presented as an extracted fact.
4. **Given** an analysis run with missing or unreadable information, **When** the run completes, **Then** the project moves to `In Review` with the incomplete items explicitly marked as assumptions, never silently fabricated.
5. **Given** a project already reviewed for round N, **When** the consultant triggers a new analysis, **Then** a new round numbered N+1 is produced that includes previously rejected items and excludes accepted/modified items from re-analysis.
6. **Given** an analysis run that cannot produce valid, well-formed proposals, **When** it fails, **Then** the run is marked failed, no partial proposal is published, and the project remains in `In Analysis` with a visible error.

---

### User Story 4 - Review a proposal round (Priority: P1)

Reviewers (Consultant and Customer HR/Business Owner) Accept, Reject, or Modify each Proposal Item. A comment is required for Reject and Modify. Accepted and modified items become locked inputs for later rounds; rejected items are re-proposed in the next round.

**Why this priority**: Human decisions are the source of accountability and the gate that lets any value reach an export.

**Independent Test**: Review one item with each action, confirm the decision is recorded with user and timestamp, confirm a Modify requires a comment, and confirm accepted items are locked and rejected items reappear in the next round.

**Acceptance Scenarios**:

1. **Given** a proposal round in `In Review`, **When** a reviewer accepts an item, **Then** the item is recorded as accepted with the deciding user and timestamp and becomes a locked input.
2. **Given** a pending item, **When** a reviewer rejects it, **Then** a comment is required and the item is marked for re-proposal in the next round.
3. **Given** a pending item, **When** a reviewer modifies it, **Then** a comment is required, the modified value is stored as the decided value, and it becomes a locked input.
4. **Given** an item already accepted or modified in an earlier round, **When** a new round is generated, **Then** the item is carried forward unchanged and is not open for re-review unless the project is explicitly reopened.

---

### User Story 5 - Validate and finalize a project (Priority: P1)

When all items are resolved and all validation rules pass, the Consultant finalizes the project. Validation covers referential integrity, no duplicate identifiers, no orphaned entities, no unresolved conflicts, and no unacknowledged assumptions.

**Why this priority**: Finalization is the correctness gate that guarantees the exported model is internally consistent and fully human-approved.

**Independent Test**: Attempt to finalize with one unresolved conflict and confirm it is blocked with the failing rule shown; resolve it and confirm finalization succeeds.

**Acceptance Scenarios**:

1. **Given** a project `In Review` with at least one pending or rejected item, **When** the consultant attempts to finalize, **Then** finalization is blocked and the unresolved items are listed.
2. **Given** all items resolved but failing any validation rule, **When** the consultant runs validation, **Then** the result is `Fail`, each failing rule is reported with the specific failing records, and finalization is blocked.
3. **Given** all items resolved and every validation rule passing, **When** the consultant finalizes, **Then** the project transitions to `Finalized` and its accepted dataset is frozen.
4. **Given** a project in `Finalized`, **When** any user attempts to change a decision, **Then** the change is rejected; the project must be reopened through the explicit reopen flow first.

---

### User Story 6 - Export a versioned implementation package (Priority: P1)

The Consultant exports the finalized project. The system produces one workbook per in-scope entity type matching the HRMS standard import template exactly, plus a Difference Report, a Validation Report, and a Decision Log, bundled as a versioned Implementation Package.

**Why this priority**: The exported package is the deliverable consumed by the System Administrator and the HRMS import tool.

**Independent Test**: Export a finalized project and confirm the package contains the exact expected files, that each workbook matches the standard template, and that it is stored under a unique version.

**Acceptance Scenarios**:

1. **Given** a project `Finalized`, **When** the consultant exports it, **Then** a package is produced containing `Companies.xlsx`, `Locations.xlsx`, `Departments.xlsx`, `CostCenters.xlsx`, `JobTitles.xlsx`, `Employees.xlsx`, `ReportingLines.xlsx`, `Roles.xlsx`, `ApprovalWorkflows.xlsx` for in-scope entity types, plus the Difference Report, Validation Report, and Decision Log.
2. **Given** the export completes, **Then** the project transitions to `Exported`, each file matches the HRMS standard import template exactly, and the package is stored under a new version number.
3. **Given** any part of export cannot be produced, **Then** the export is all-or-nothing: no partial package is published and the project remains `Finalized`.
4. **Given** a project that has been exported before, **When** it is exported again after reopening, **Then** a new package version is produced and no prior package version is overwritten or removed.

---

### User Story 7 - Trace the provenance of any exported value (Priority: P2)

Any user, including the System Administrator, can select a value in an exported package and see where it came from and who approved it.

**Why this priority**: Traceability is a stated non-functional priority and the reason the workflow is trustworthy, but it depends on the export flow above.

**Independent Test**: Choose a cell in an exported workbook and retrieve its originating document reference and the decision (who, what action, when).

**Acceptance Scenarios**:

1. **Given** an exported value derived from a document, **When** a user inspects its provenance, **Then** the system shows the source document, version, and location, plus the decision action, deciding user, and timestamp.
2. **Given** an exported value that was treated as an assumption, **When** a user inspects it, **Then** the Assumption flag and its acknowledgement decisively distinguish it from extracted facts.

---

### User Story 8 - Monitor project progress (Priority: P2)

The Implementation Project Manager monitors the progress of all projects they are assigned to: lifecycle status, round number, open/resolved/conflicting item counts, and validation state.

**Why this priority**: Visibility supports delivery management, but the workflow functions without it.

**Independent Test**: Assign a project manager to a project, move the project through rounds, and confirm the reported status and counts update accordingly.

**Acceptance Scenarios**:

1. **Given** a project manager assigned to a project, **When** they open the project overview, **Then** they can see lifecycle status, current round, and counts of pending, accepted, rejected, conflicting, and assumption items.
2. **Given** a user who is not a member of a project, **When** they attempt to view it, **Then** access is denied.

---

### User Story 9 - Reopen an exported project (Priority: P2)

The Consultant explicitly reopens an exported project to make further changes. The reopen is logged, produces a new version on the next export, and never overwrites prior packages.

**Why this priority**: Needed for real-world correction cycles, but the happy path is complete without it.

**Independent Test**: Reopen an exported project, make a change and export again, and confirm the reopen is logged and both package versions coexist.

**Acceptance Scenarios**:

1. **Given** a project in `Exported`, **When** the consultant explicitly confirms a reopen, **Then** the project returns to `In Review`, the reopen is recorded in the audit history with actor and timestamp, and the project becomes editable again.
2. **Given** a reopened project, **When** it is exported again, **Then** the new package receives the next version number and all prior packages remain intact.

---

### User Story 10 - Choose the AI provider per project (Priority: P3)

Each project has an AI provider setting of `OPENAI` or `LOCAL_QWEN`. Analysis results and behavior do not depend on which provider is selected.

**Why this priority**: Required for data-residency compliance, but it is a project setting, not a separate workflow.

**Independent Test**: Run the same fixed document set through the same project under each provider and confirm the workflow, proposal structure, validation, and export outcomes are equivalent.

**Acceptance Scenarios**:

1. **Given** a project being configured, **When** the consultant selects an AI provider, **Then** that provider is stored on the project and used for that project's analysis runs only.
2. **Given** the same inputs analyzed under each supported provider, **When** the runs complete, **Then** both produce the same proposal-item structure, validation behavior, and export format.

---

### Edge Cases

- A project with zero in-scope documents when analysis is triggered: the run does not silently succeed; the user is informed there is nothing to analyze.
- A document is replaced while an analysis run is in progress: the run uses the version snapshot captured at trigger time; the replacement applies to the next run.
- Every alternative for a conflicted value is rejected or modified inconsistently: the conflict remains open and blocks finalization until it is deliberately resolved by a recorded human decision.
- A reviewer modifies an item to a value that later breaks referential integrity: validation catches it and blocks finalization.
- Two entity types in scope reference each other (e.g., Employees and Reporting Lines) but one side is out of scope: validation reports the orphaned reference rather than dropping it.
- A provider is unavailable or returns malformed output: the run fails loudly; no partial proposal is published and no value reaches the accepted dataset.
- Reopening, changing a decision, and re-exporting after the implementing team has already consumed a package: prior packages remain unchanged and versioned so the consumer can detect the new version.
- The same person holds multiple roles (e.g., consultant and customer owner): decisions are attributed to the acting user and permission is checked per action, not per person.
- A user not assigned to a project attempts any action: access is denied regardless of their global role.

## Requirements *(mandatory)*

### Functional Requirements

**Project setup and scope**

- **FR-001**: The system MUST allow a permitted user to create a Workshop Project for a customer with a name, a selected set of in-scope entity types, and an AI provider.
- **FR-002**: The system MUST support exactly these entity types as scope choices: Companies, Locations, Departments, Cost Centers, Job Titles, Employees, Reporting Lines, Roles, Approval Workflows.
- **FR-003**: The system MUST restrict every project action to users who hold an explicit membership on that project with a role (Consultant, Customer Reviewer, Project Manager, Administrator), in addition to platform-level permissions.
- **FR-004**: The system MUST record the creator and creation time of a project, and restrict create/configure, upload, trigger analysis, review, finalize, export, and reopen to the permitted roles.

**Documents**

- **FR-005**: The system MUST allow permitted users to upload source documents in PDF, Word, Excel, CSV, and scanned image formats and tag each with a document type.
- **FR-006**: The system MUST version documents on upload or replacement; a replaced version MUST be marked `Superseded` and MUST remain retrievable; documents and versions MUST NOT be deleted.
- **FR-007**: The system MUST record for each version the uploader, timestamp, file name, and a content checksum, and MUST reject unsupported or unreadable files without changing project state.
- **FR-008**: The system MUST record each analysis run's exact set of input document versions so results can be traced to the evidence used.

**Analysis and proposals**

- **FR-009**: The system MUST allow a permitted user to trigger an Analysis Run that extracts business facts, detects conflicts between documents, detects likely duplicates, recommends mappings to the HRMS standard model, and recommends organization structure, reporting lines, approval structures, and department/job-title normalization.
- **FR-010**: The system MUST produce, for each successful analysis run, exactly one new numbered Proposal Round made of Proposal Items.
- **FR-011**: Each Proposal Item MUST include the proposed value, a plain-language explanation, a confidence level, source references (document, version, and location), and an explicit Assumption flag when information is missing.
- **FR-012**: The system MUST NOT resolve conflicts; every conflicting item MUST show each alternative with its source and remain unresolved until a human decides.
- **FR-013**: The system MUST infer values only where necessary and MUST flag every inferred value as an Assumption, never presenting it as an extracted fact.
- **FR-014**: The system MUST fail an Analysis Run that cannot produce valid, well-formed proposals, MUST NOT publish a partial proposal, and MUST surface the failure to the user.
- **FR-015**: The system MUST treat accepted and modified items as locked inputs that are carried forward unchanged and are not re-analyzed in later rounds.
- **FR-016**: The system MUST include previously rejected items in the next round's analysis input.

**Review and decisions**

- **FR-017**: The system MUST allow permitted reviewers to Accept, Reject, or Modify each Proposal Item, and MUST require a comment for Reject and Modify.
- **FR-018**: The system MUST record every decision as immutable history with the action, resulting value, comment, deciding user, and timestamp, and MUST NOT overwrite prior decisions.

**Lifecycle**

- **FR-019**: The system MUST enforce a fixed lifecycle of Setup, Collecting Documents, In Analysis, In Review, Finalized, Exported, allowing only these transitions: Setup→Collecting Documents, Collecting Documents→In Analysis, In Analysis→In Review, In Review→Finalized, In Review→In Analysis, Finalized→Exported, Exported→In Review (explicit reopen only).
- **FR-020**: The system MUST allow `In Review → In Analysis` to start a new analysis round and MUST allow `In Review → Finalized` only when no item is pending or rejected and all validation rules pass.
- **FR-021**: The system MUST make an exported project read-only and MUST allow editing only after an explicit, logged reopen that produces a new package version on the next export.

**Validation**

- **FR-022**: The system MUST validate the accepted dataset against these rules: referential integrity, no duplicate identifiers, no orphaned entities, no unresolved conflicts, and no unacknowledged assumptions.
- **FR-023**: The system MUST report each validation result as pass or fail with the specific failing records, MUST require all rules to pass before finalization, and MUST support re-running validation during review.

**Export**

- **FR-024**: The system MUST, for a finalized project, export one workbook per in-scope entity type named `Companies.xlsx`, `Locations.xlsx`, `Departments.xlsx`, `CostCenters.xlsx`, `JobTitles.xlsx`, `Employees.xlsx`, `ReportingLines.xlsx`, `Roles.xlsx`, and `ApprovalWorkflows.xlsx`, each matching the HRMS standard import template exactly, plus a Difference Report, a Validation Report, and a Decision Log.
- **FR-025**: The system MUST bundle all export artifacts into a versioned Implementation Package, MUST make export all-or-nothing, and MUST NOT overwrite or delete prior package versions.
- **FR-026**: The system MUST NOT write to production HRMS data and MUST NOT perform the import; the package is handed off to the consuming import process.

**Traceability and audit**

- **FR-027**: The system MUST allow any exported value to be traced to its source reference (or Assumption flag) and to the decision, user, and timestamp that approved it.
- **FR-028**: The system MUST maintain a permanent, append-only audit history of project setup, document uploads, analysis runs, decisions, validation runs, finalization, exports, and reopens.

**AI provider independence**

- **FR-029**: The system MUST store an AI provider setting of `OPENAI` or `LOCAL_QWEN` per project, MUST use it for that project's analysis, and MUST NOT store provider credentials on the project.
- **FR-030**: The system's analysis behavior, proposal structure, validation, and export MUST NOT depend on which supported AI provider is selected.

### Key Entities *(include if feature involves data)*

- **Workshop Project**: A discovery engagement for one customer; holds name, lifecycle status, selected in-scope entity types, AI provider setting, current round number, creator, and timestamps.
- **Project Member**: Assignment of a user to a project with a role (Consultant, Customer Reviewer, Project Manager, Administrator); gates all project access.
- **Source Document**: A logical document in a project, with a type/tag, status (Uploaded, Analyzed, Superseded), and a pointer to its current version.
- **Document Version**: An immutable uploaded file revision with version number, storage location, file name, checksum, uploader, upload time, and superseded time.
- **Analysis Run**: A triggered analysis over a captured snapshot of active document versions; has status, provider used, input snapshot, and error details.
- **Proposal Round**: The immutable result of one successful analysis run; numbered, belongs to a project, contains Proposal Items.
- **Proposal Item**: One proposed entity value; holds entity type, a stable logical key across rounds, proposed value, explanation, confidence, source references, Assumption flag, conflict flag and alternatives, and a link to any carried-forward prior item.
- **Decision**: An immutable human action (Accept, Reject, Modify) on a Proposal Item, with resulting value, comment, deciding user, and timestamp.
- **Validation Run**: A validation of the accepted dataset with an overall pass/fail result.
- **Validation Result**: One rule's outcome within a validation run, with failing records when relevant.
- **Export Package**: A versioned bundle of export artifacts for a project, with version number, storage location, exporter, and export time.
- **Audit Event**: An append-only record of a significant action on a project, with actor, action, affected entity, and timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A typical customer implementation can reach an agreed, exported model in 2-3 review rounds, versus the current many-meeting manual process.
- **SC-002**: 100% of exported values can be traced to a source reference or an explicit Assumption flag, and to the user and timestamp of the approving decision, within one minute of inspection.
- **SC-003**: 100% of conflicts are surfaced with all alternatives and no conflict is auto-resolved by the system.
- **SC-004**: 0 exported packages contain a value that no human explicitly accepted or modified.
- **SC-005**: 100% of validation failures report the specific failing records and block finalization until resolved.
- **SC-006**: Re-running the same fixed document set produces structurally equivalent proposals (same entity types, items, and flags) regardless of which supported AI provider is selected.
- **SC-007**: Every project is fully reconstructable to any prior round or package version from permanent history, with no prior records lost.
- **SC-008**: An export never produces a partial package: either all expected files are present and template-matching, or no package is produced.
- **SC-009**: A reviewer can process a round of proposals without training on internal terminology, guided by plain-language explanations and confidence levels.
- **SC-010**: No unauthorized user can view or act on a project they are not a member of, verified across all project actions.

## Assumptions

- The module reuses the existing HRMS platform's authentication and global role/permission model; only project-scoped membership is added.
- The HRMS standard import templates are fixed and available to the module; the export must match them, and this spec treats their field definitions as an external dependency rather than redefining them here.
- "Signed off" by the Customer HR/Business Owner is expressed through their decisions (Accept/Modify) during review; no separate electronic-signature mechanism is in scope.
- Analysis runs are asynchronous; users may leave and return while a run completes.
- Only the active (non-Superseded) document versions participate in an analysis run, snapshotted at trigger time.
- Each analysis run produces exactly one proposal round; failed runs produce none.
- Concurrent editing of the same proposal item is not supported; the workflow assumes reviewers act on their assigned project without real-time collaboration.
- Document OCR/extraction confidence is folded into the proposal confidence level; a low-quality source read cannot yield a high-confidence proposal.
- Data volume is small (a handful of projects per customer per year, hundreds to low thousands of items per project); performance and scale optimization are explicitly out of scope.
- Data retention follows the platform's existing retention policy; within the module, history is permanent and append-only.
- The exported package is consumed by a separate, existing HRMS import process; performing the import and writing to production HRMS data are explicitly out of scope.
- Document management is limited to workshop artifacts; the module is not a general document management system. Compensation/benefits data, a workflow builder, and real-time collaborative editing are out of scope.
