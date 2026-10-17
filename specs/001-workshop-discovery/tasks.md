---
description: "Task list for Workshop Module — AI-Assisted Discovery Workflow"
---

# Tasks: Workshop Module — AI-Assisted Discovery Workflow

**Input**: Design documents from `/specs/001-workshop-discovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Included — the task request explicitly asks for tests covering state transitions, validation rules, AI-response schema validation, and export all-or-nothing behavior. Write tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story (from spec.md) to allow independent implementation and testing. Within each story: tests → models → services → endpoints → integration.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Every task includes an exact file path

## Path Conventions

Single project: `src/workshop/`, `tests/`, migrations in `migrations/`, feature docs in `specs/001-workshop-discovery/`. All paths are relative to the repository root, matching plan.md.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and skeleton so later tasks have a home.

- [X] T001 Initialize the uv project for Python 3.12 and declare all runtime/dev dependencies (FastAPI, uvicorn, pydantic v2, pydantic-settings, SQLAlchemy 2, Alembic, Arq, PyJWT, boto3, confluent-kafka, structlog, pandas, openpyxl, xlrd, pdfplumber, python-docx, pytesseract, openai, instructor, rapidfuzz, httpx) in `pyproject.toml`
- [X] T002 [P] Create the package skeleton and empty `__init__.py` files for every module in `src/workshop/` (main, worker, settings, db, logging, auth, common, project, document, parsing, ai, analysis, proposal, review, validation, export, audit, events) per plan.md
- [X] T003 [P] Create the test tree with `tests/unit/`, `tests/integration/`, `tests/contract/`, and `tests/fixtures/sample_documents/` (add `.gitkeep` placeholders, no fixture content yet)
- [X] T004 [P] Configure ruff (lint + format) and mypy (strict, Python 3.12) in `pyproject.toml`
- [X] T005 [P] Configure pytest and testcontainers fixtures baseline (PostgreSQL + MinIO) in `tests/conftest.py`
- [X] T006 [P] Create the single-image `Dockerfile` with two commands (API: `uvicorn workshop.main:app`; worker: `arq workshop.worker.WorkerSettings`) in `Dockerfile`
- [X] T007 [P] Create `.env.example` documenting DB URL, Redis URL, S3 endpoint/credentials/bucket, JWT settings, Kafka bootstrap, and AI provider keys in `.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure and the full database schema. **No user story can begin until this phase is complete.**

**⚠️ CRITICAL**: All models are created here (one migration for the whole `workshop` schema) because every story depends on the schema; per-story service logic follows in each story phase.

- [X] T008 Implement settings via pydantic-settings (DB URL, Redis URL, S3 config, JWT issuer/audience/key-or-JWKS, Kafka bootstrap/topic, AI provider config, presign TTL, duplicate-similarity threshold, analysis timeout) in `src/workshop/settings.py`
- [X] T009 Configure structlog JSON logging in `src/workshop/logging.py`
- [X] T010 [P] Define all shared enums — `ProjectStatus`, `DocumentStatus`, `AnalysisRunStatus`, `DecisionAction`, `Confidence`, `ValidationOutcome`, `EntityType`, `AIProvider`, `ProjectRole` — with exact values from data-model.md in `src/workshop/common/enums.py`
- [X] T011 [P] Define domain exceptions and map them to RFC 9457 `application/problem+json` (403/404/409/422) exception handlers in `src/workshop/common/errors.py`
- [X] T012 [P] Create shared pydantic base models and pagination types in `src/workshop/common/types.py`
- [X] T013 Implement the SQLAlchemy engine/session factory and set the session `search_path` to `workshop, public` in `src/workshop/db.py`
- [X] T014 [P] Create `WorkshopProject` and `WorkshopProjectMember` models per data-model.md (status default `Setup`, `current_round` default 0, `reopen_count` default 0, unique `(project_id, user_id, role)`) in `src/workshop/project/models.py`
- [X] T015 [P] Create `WorkshopDocument` and `WorkshopDocumentVersion` models per data-model.md (unique `(document_id, version_number)`, `upload_status`, `checksum_sha256`, `superseded_at`) in `src/workshop/document/models.py`
- [X] T016 [P] Create `WorkshopAnalysisRun` model per data-model.md (`document_version_ids UUID[]`, `prior_decision_ids`, `ai_provider`, `error_message`) in `src/workshop/analysis/models.py`
- [X] T017 [P] Create `WorkshopProposal` and `WorkshopProposalItem` models per data-model.md (JSONB `proposed_value`, `source_refs`, `conflict_alternatives`; `carried_from_item_id` self-FK; unique `(project_id, round_number)`) in `src/workshop/proposal/models.py`
- [X] T018 [P] Create `WorkshopDecision` model per data-model.md (insert-only; `action`, `resulting_value` JSONB, `comment`, `decided_by`, `decided_at`, `reopened`) in `src/workshop/review/models.py`
- [X] T019 [P] Create `WorkshopValidationRun` and `WorkshopValidationResult` models per data-model.md (`rule_code`, `result`, `failing_records` JSONB) in `src/workshop/validation/models.py`
- [X] T020 [P] Create `WorkshopExportPackage` model per data-model.md (unique `(project_id, version_number)`, `storage_prefix`, `files` JSONB) in `src/workshop/export/models.py`
- [X] T021 [P] Create the append-only `WorkshopAuditLog` model per data-model.md (`action`, `entity_type`, `entity_id`, `payload` JSONB, `occurred_at`) in `src/workshop/audit/models.py`
- [X] T022 Configure Alembic (`version_table_schema="workshop"`, schema-qualified) and write the single initial migration creating the `workshop` schema and all tables/indexes from T014–T021 in `migrations/` and `alembic.ini`
- [X] T023 Implement JWT verification with PyJWT (shared key or JWKS; extract `sub`, `tenant_id`, global roles) in `src/workshop/auth/jwt.py`
- [X] T024 [P] Define the `AuthenticatedUser` model in `src/workshop/auth/models.py`
- [X] T025 Implement the single `require_project_role(*roles)` FastAPI dependency (validates token, loads `workshop_project_member`, checks role and tenant match) in `src/workshop/auth/dependencies.py`
- [X] T026 Implement the audit service (append-only writer + query) in `src/workshop/audit/service.py`
- [X] T027 Implement the outbound Kafka producer (`workshop.finalized`, `workshop.exported`) in `src/workshop/events/producer.py`
- [X] T028 [P] Implement the FastAPI app factory, router registration, exception handlers, and `/health` in `src/workshop/main.py`
- [X] T029 [P] Implement Arq `WorkerSettings` and job registration skeleton in `src/workshop/worker.py`
- [X] T030 [P] Unit test: audit service writes append-only rows and tenant-filters reads in `tests/unit/audit/test_audit_service.py`
- [X] T031 [P] Integration test: migration applies cleanly and the `workshop` schema/tables exist in `tests/integration/test_schema_migration.py`

**Checkpoint**: Foundation ready — user story phases can now begin.

---

## Phase 3: User Story 1 - Create a Workshop Project and define scope (Priority: P1) 🎯 MVP

**Goal**: A consultant creates a project, selects in-scope entity types and AI provider, and drives the fixed lifecycle from `Setup`.

**Independent Test**: Create a project with a subset of entity types, confirm status `Setup`, update config while in `Setup`, transition to `Collecting Documents`, and confirm disallowed transitions fail.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T032 [P] [US1] Unit test the lifecycle transition table and guard failures (only `Setup→Collecting Documents`, etc.; `In Review→Finalized` blocked without resolved items/passing validation) in `tests/unit/project/test_lifecycle.py`
- [X] T033 [P] [US1] Integration test create/list/get/update/transition with membership enforcement (non-member gets 403) in `tests/integration/test_project_lifecycle.py`

### Implementation for User Story 1

- [X] T034 [P] [US1] Implement `ALLOWED_TRANSITIONS`, `assert_transition`, and guard functions (`Setup→Collecting Documents` requires non-empty scope and ≥1 member) in `src/workshop/project/lifecycle.py`
- [X] T035 [P] [US1] Implement request/response schemas (`ProjectCreate` with `scopedEntityTypes minItems:1 uniqueItems`, `ProjectUpdate`, `Project`, `ProjectPage`, `TransitionRequest`) in `src/workshop/project/schemas.py`
- [X] T036 [US1] Implement the project service (create with creator as CONSULTANT member, get, list by membership, update while `Setup`, transition with audit writes) in `src/workshop/project/service.py`
- [X] T037 [US1] Implement the member service (add/list/remove, role validation) in `src/workshop/project/member_service.py`
- [X] T038 [US1] Implement project + member endpoints from `contracts/openapi.yaml` in `src/workshop/project/router.py`

**Checkpoint**: US1 fully functional and testable independently (MVP).

---

## Phase 4: User Story 2 - Collect, version, and tag source documents (Priority: P1)

**Goal**: Upload/tag documents, create versions, mark prior versions superseded (never delete), and parse deterministically into `ExtractedFact`s with source references.

**Independent Test**: Create a document and version 1, replace it (version 2; version 1 superseded but retrievable), complete an upload, get a download URL, and parse CSV/XLSX/PDF/DOCX fixtures into source-referenced facts.

### Tests for User Story 2 ⚠️

- [X] T039 [P] [US2] Unit test extractors: `dtype=str` preserves codes like `00123`, and PDF/DOCX/CSV outputs carry correct page/sheet/row/cell in `tests/unit/parsing/test_extractors.py`
- [X] T045 [P] [US2] Integration test document create → complete → replace → supersede and download URL in `tests/integration/test_documents.py`

### Implementation for User Story 2

- [X] T041 [P] [US2] Implement the S3/MinIO adapter (`workshop/{tenant}/{project}/documents/{doc}/{version}/{filename}` keys, pre-signed PUT/GET) in `src/workshop/document/storage.py`
- [X] T042 [P] [US2] Implement document request/response schemas (`DocumentCreate`, `DocumentVersionCreate`, `DocumentUploadTicket`, `DocumentVersion`, `Document`, `DocumentDetail`, `DownloadUrl`) in `src/workshop/document/schemas.py`
- [X] T043 [P] [US2] Implement `ExtractedFact` and `SourceRef` models in `src/workshop/parsing/models.py`
- [X] T044 [P] [US2] Implement the `Extractor` Protocol and `ExtractorFactory` (select by mime type) in `src/workshop/parsing/extractors/base.py`
- [X] T046 [P] [US2] Implement the tabular extractor (pandas + openpyxl, `dtype=str`) in `src/workshop/parsing/extractors/tabular_extractor.py`
- [X] T047 [P] [US2] Implement the PDF extractor (pdfplumber, page/position refs) in `src/workshop/parsing/extractors/pdf_extractor.py`
- [X] T048 [P] [US2] Implement the DOCX extractor (python-docx, paragraphs + tables) in `src/workshop/parsing/extractors/docx_extractor.py`
- [X] T049 [P] [US2] Implement the scan/OCR extractor (pytesseract) returning OCR confidence in `src/workshop/parsing/extractors/image_ocr_extractor.py`
- [X] T050 [US2] Implement the parsing service (route by mime, exclude-and-flag a failed document, fail the run only if it was the sole document) in `src/workshop/parsing/service.py`
- [X] T051 [US2] Implement the document service (create doc+version 1, completion with checksum, replace/supersede, list, get with versions, download URL; audit writes) in `src/workshop/document/service.py`
- [X] T052 [US2] Implement document endpoints from `contracts/openapi.yaml` in `src/workshop/document/router.py`
- [X] T053 [US2] Add fixed sample documents and an expected-extraction fixture set (PDF, DOCX, XLSX, CSV, scan) in `tests/fixtures/sample_documents/`

**Checkpoint**: US2 works independently; parsed facts are source-referenced.

---

## Phase 5: User Story 3 - Analysis Run produces a proposal round (Priority: P1)

**Goal**: Trigger an analysis run that extracts facts, detects conflicts and duplicates deterministically, recommends mappings, and produces a numbered proposal round with explanations, confidence, source refs, and assumption/conflict flags — never auto-resolving conflicts.

**Independent Test**: With the sample documents and a `FakeAIClient`, trigger a run and confirm a proposal round with items and flags; force AI/schema failure and confirm the run is `Failed` with no proposal persisted.

### Tests for User Story 3 ⚠️

- [X] T054 [P] [US3] Unit test AI-response schema validation rejects malformed/partial output and accepts valid output in `tests/unit/ai/test_schemas.py`
- [X] T055 [P] [US3] Unit test deterministic conflict detection (same `entity_key`, differing values → flagged, no winner) and duplicate detection (rapidfuzz threshold) in `tests/unit/analysis/test_detection.py`
- [X] T056 [P] [US3] Integration test the full analysis run with `FakeAIClient` (proposal round created, project → `In Review`) in `tests/integration/test_analysis_run.py`
- [X] T057 [P] [US3] Integration test AI failure and schema-invalid output → run `Failed`, error recorded, no `WorkshopProposal`/items persisted, project stays `In Analysis` in `tests/integration/test_analysis_failure.py`

### Implementation for User Story 3

- [X] T058 [P] [US3] Implement the pydantic structured-output schemas for extraction/mapping/explanation in `src/workshop/ai/schemas.py`
- [X] T059 [P] [US3] Define the `AIClient` Protocol with `extract_facts`, `recommend_mapping`, `explain`, plus request/response models in `src/workshop/ai/client.py`
- [X] T060 [P] [US3] Implement prompt template functions in `src/workshop/ai/prompts.py`
- [X] T061 [P] [US3] Implement `FakeAIClient` (deterministic, schema-valid, configurable to fail) in `src/workshop/ai/fake.py`
- [X] T062 [US3] Implement `OpenAIClient` using the openai SDK + instructor (schema validation, retry-once) in `src/workshop/ai/providers/openai_client.py`
- [X] T063 [P] [US3] Implement `LocalQwenClient` (vLLM OpenAI-compatible base URL, same behavior) in `src/workshop/ai/providers/local_qwen_client.py`
- [X] T064 [US3] Implement the provider factory resolving `AIClient` from `project.ai_provider` in `src/workshop/ai/factory.py`
- [X] T065 [US3] Implement `extract-facts.step` (call `AIClient.extract_facts` per in-scope entity type, carry locked items forward) in `src/workshop/analysis/steps/extract_facts.py`
- [X] T066 [P] [US3] Implement `detect-conflicts.step` (structural set comparison by `entity_key`+field → `conflict_alternatives`) in `src/workshop/analysis/steps/detect_conflicts.py`
- [X] T067 [P] [US3] Implement `detect-duplicates.step` (rapidfuzz similarity, sets `likely_duplicate_of`) in `src/workshop/analysis/steps/detect_duplicates.py`
- [X] T068 [P] [US3] Implement `recommend-mapping.step` (semantic mapping/normalization via `AIClient.recommend_mapping`) in `src/workshop/analysis/steps/recommend_mapping.py`
- [X] T069 [US3] Implement `build-proposal.step` (deterministic `entity_key`, assumption flags, `carried_from_item_id`, re-proposed rejected keys) in `src/workshop/analysis/steps/build_proposal.py`
- [X] T070 [US3] Implement the analysis orchestrator (`src/workshop/analysis/service.py`) wiring steps, provider-agnostic, in one transaction
- [X] T071 [US3] Implement the Arq task `process_analysis_run` (status `Queued→Running→Completed|Failed`, atomic persist, fail loud, set project `In Review` on success) in `src/workshop/analysis/jobs.py`
- [X] T072 [US3] Implement analysis endpoints (trigger `202`, status, list, retry) from `contracts/openapi.yaml` in `src/workshop/analysis/router.py`
- [X] T073 [P] [US3] Implement the accepted-dataset derived query (latest Accept/Modify per `entity_key`, reopened excluded) and round comparison in `src/workshop/proposal/service.py`
- [X] T074 [P] [US3] Implement proposal schemas (`ProposalItem`, `ProposalRound`, `ProposalRoundSummary`, `RoundComparison`) in `src/workshop/proposal/schemas.py`
- [X] T075 [US3] Implement proposal endpoints (list rounds, get round with items and state, compare) in `src/workshop/proposal/router.py`

**Checkpoint**: US3 works independently against the `FakeAIClient`.

---

## Phase 6: User Story 4 - Review a proposal round (Priority: P1)

**Goal**: Accept/Reject/Modify items with comment required for Reject/Modify; accepted/modified items are locked inputs; rejected items are re-proposed.

**Independent Test**: Record one decision of each action, verify comment enforcement and immutable decision history, verify item state, and verify locked carry-forward and rejected re-proposal.

### Tests for User Story 4 ⚠️

- [X] T076 [P] [US4] Unit test comment-required rules (Reject/Modify without comment → 422) and item-resolution logic in `tests/unit/review/test_decision_rules.py`
- [X] T077 [P] [US4] Integration test decisions are insert-only, item state updates, and locked items carry forward while rejected items reappear in the next round in `tests/integration/test_review.py`

### Implementation for User Story 4

- [X] T078 [P] [US4] Implement decision schemas (`DecisionCreate` with conditional comment/resultingValue rules, `Decision`) in `src/workshop/review/schemas.py`
- [X] T079 [US4] Implement the review service (record immutable decision, enforce comment rules, audit write, do not overwrite prior decisions) in `src/workshop/review/service.py`
- [X] T080 [US4] Implement review endpoints (record decision, list decisions) from `contracts/openapi.yaml` in `src/workshop/review/router.py`
- [X] T081 [US4] Wire item-state projection (`Pending`/`Accepted`/`Rejected`/`Modified` + `latestDecision`) into the proposal read model in `src/workshop/proposal/service.py`

**Checkpoint**: US4 works independently.

---

## Phase 7: User Story 5 - Validate and finalize (Priority: P1)

**Goal**: Run the five validation rules over the accepted dataset; block finalization until all items are resolved and every rule passes.

**Independent Test**: Finalize with an unresolved conflict → blocked with failing rule listed; resolve and pass all rules → project becomes `Finalized`.

### Tests for User Story 5 ⚠️

- [X] T082 [P] [US5] Unit test each rule in isolation (referential integrity, duplicate identifiers, orphaned entities, unresolved conflicts, unacknowledged assumptions) and that a rule exception → `Fail` in `tests/unit/validation/test_rules.py`
- [X] T083 [P] [US5] Integration test finalization guard: blocked when items unresolved or rules fail; succeeds when all pass in `tests/integration/test_finalization.py`

### Implementation for User Story 5

- [X] T084 [P] [US5] Define the `ValidationRule` Protocol and `ValidationRuleResult` in `src/workshop/validation/base.py`
- [X] T085 [P] [US5] Implement the five rule classes with codes `REFERENTIAL_INTEGRITY`, `DUPLICATE_IDENTIFIER`, `ORPHANED_ENTITY`, `UNRESOLVED_CONFLICT`, `UNACKNOWLEDGED_ASSUMPTION` in `src/workshop/validation/rules.py`
- [X] T086 [P] [US5] Implement the rule registry in `src/workshop/validation/registry.py`
- [X] T087 [US5] Implement the validation service (load accepted dataset, evaluate rules, persist run + results, `Pass` only if all pass) in `src/workshop/validation/service.py`
- [X] T088 [US5] Implement validation endpoints (run, list, latest) from `contracts/openapi.yaml` in `src/workshop/validation/router.py`
- [X] T089 [US5] Implement the `In Review→Finalized` guard (no pending/rejected items AND latest validation `Pass`) and finalize action/audit in `src/workshop/project/service.py`

**Checkpoint**: US5 works independently.

---

## Phase 8: User Story 6 - Export a versioned implementation package (Priority: P1)

**Goal**: Produce the nine entity workbooks plus Difference/Validation/Decision reports, template-exact, bundled as a versioned package, all-or-nothing.

**Independent Test**: Export a finalized project and confirm the exact artifact set, template match, and versioning; force a generator failure and confirm no files uploaded and no package row created.

### Tests for User Story 6 ⚠️

- [X] T090 [P] [US6] Unit test all-or-nothing: any generator failure → nothing uploaded and no package row; success → package row with complete file list in `tests/unit/export/test_all_or_nothing.py`
- [X] T091 [P] [US6] Integration test export package contents, exact filenames for in-scope entity types, template header match, and download URLs in `tests/integration/test_export.py`

### Implementation for User Story 6

- [X] T092 [P] [US6] Define the HRMS standard import template headers/column order per entity type in `src/workshop/export/templates/__init__.py`
- [X] T093 [P] [US6] Implement the entity workbook generator (`Companies.xlsx` … `ApprovalWorkflows.xlsx`, in-scope only, template-exact) in `src/workshop/export/generators/excel_package.py`
- [X] T094 [P] [US6] Implement the Difference Report generator (final vs original source value, using `source_refs` + `is_assumption`) in `src/workshop/export/generators/difference_report.py`
- [X] T095 [P] [US6] Implement the Validation Report generator (latest passing run) in `src/workshop/export/generators/validation_report.py`
- [X] T096 [P] [US6] Implement the Decision Log generator (all decisions chronological) in `src/workshop/export/generators/decision_log.py`
- [X] T097 [US6] Implement the export service (temp-build, all-or-nothing upload to `exports/v{n}/`, package row, `Finalized→Exported`, `workshop.exported` event) in `src/workshop/export/service.py`
- [X] T098 [US6] Implement export endpoints (create/get/list, file download URL) from `contracts/openapi.yaml` in `src/workshop/export/router.py`

**Checkpoint**: US6 works independently; core P1 flow complete end-to-end.

---

## Phase 9: User Story 7 - Trace the provenance of any exported value (Priority: P2)

**Goal**: Any exported value answers "where did it come from and who approved it".

**Independent Test**: For a chosen exported value, retrieve its source reference (document version, page/sheet, row/cell) and the accepting decision (user, action, timestamp).

### Tests for User Story 7 ⚠️

- [X] T099 [P] [US7] Integration test: exported value → `source_refs` and latest decision (user, action, timestamp); assumption values distinguishable from extracted facts in `tests/integration/test_traceability.py`

### Implementation for User Story 7

- [X] T100 [US7] Implement a traceability read endpoint returning an item's `sourceRefs` and decision chain in `src/workshop/proposal/router.py` (add `GET /projects/{projectId}/proposal-items/{itemId}/trace` to `contracts/openapi.yaml`)
- [X] T101 [US7] Include a provenance column (source file + approving user) in the generated workbooks and Difference Report in `src/workshop/export/generators/excel_package.py`, `src/workshop/export/generators/difference_report.py`

**Checkpoint**: US7 works independently.

---

## Phase 10: User Story 8 - Monitor project progress (Priority: P2)

**Goal**: Project Manager sees lifecycle status, current round, and open/resolved/conflicting/assumption counts.

**Independent Test**: Assign a PM, advance the project, and confirm `ProjectOverview` counts update.

### Tests for User Story 8 ⚠️

- [X] T102 [P] [US8] Integration test overview counts (pending/accepted/rejected/modified/conflicts/assumptions, validation state) and 403 for non-members in `tests/integration/test_project_overview.py`

### Implementation for User Story 8

- [X] T103 [US8] Implement the project overview service (aggregate counts + validation state + document counts) in `src/workshop/project/overview_service.py`
- [X] T104 [US8] Implement the overview endpoint (`GET /projects/{projectId}/overview`) in `src/workshop/project/router.py`

**Checkpoint**: US8 works independently.

---

## Phase 11: User Story 9 - Reopen an exported project (Priority: P2)

**Goal**: Explicit, logged reopen returns `Exported` to `In Review`; the next export is a new version and prior packages remain intact.

**Independent Test**: Reopen, change a decision, export again, and confirm the reopen is audited and both package versions coexist.

### Tests for User Story 9 ⚠️

- [X] T105 [P] [US9] Unit test reopen transitions and `reopen_count` increment in `tests/unit/project/test_reopen.py`
- [X] T106 [P] [US9] Integration test reopen → change → re-export creates a new package version while prior versions and files are untouched in `tests/integration/test_reopen_reexport.py`

### Implementation for User Story 9

- [X] T107 [US9] Implement the reopen service (only from `Exported`, reason required, audit `PROJECT_REOPENED`, increment `reopen_count`, mark affected decisions `reopened`) in `src/workshop/project/reopen_service.py`
- [X] T108 [US9] Implement the reopen endpoint (`POST /projects/{projectId}/reopen`) in `src/workshop/project/router.py`

**Checkpoint**: US9 works independently.

---

## Phase 12: User Story 10 - Choose the AI provider per project (Priority: P3)

**Goal**: Project-level `OPENAI`/`LOCAL_QWEN` selection with no behavioral difference in analysis logic.

**Independent Test**: Run the same fixed sample set through both providers and confirm equivalent proposal structure, validation behavior, and export format.

### Tests for User Story 10 ⚠️

- [X] T109 [P] [US10] Integration test the AI regression set against both providers, confirming provider-independent item structure (skip when provider credentials are absent) in `tests/integration/test_ai_regression.py`

### Implementation for User Story 10

- [X] T110 [US10] Ensure provider is resolved per run and never leaks into analysis code; add a test asserting the orchestrator depends only on the `AIClient` Protocol in `tests/unit/ai/test_provider_independence.py`

**Checkpoint**: US10 works independently.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Contract, quality gates, and documentation across stories.

- [X] T111 [P] Add the OpenAPI snapshot contract test (generated spec vs `specs/001-workshop-discovery/contracts/openapi.yaml`) in `tests/contract/test_openapi_snapshot.py`
- [X] T112 [P] Add a client-generation smoke test (generate a TypeScript client from the OpenAPI document) in `tests/contract/test_client_generation.py`
- [X] T113 [P] Enforce tenant isolation across all read endpoints (unit tests asserting non-member/cross-tenant denial) in `tests/integration/test_tenant_isolation.py`
- [X] T114 [P] Run `ruff check`, `ruff format --check`, and `mypy` and resolve all findings across `src/workshop/`
- [ ] T115 [P] Validate `specs/001-workshop-discovery/quickstart.md` end-to-end against the running service
- [X] T116 [P] Write the service README (configuration, running API/worker, migrations, OpenAPI generation) in `README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories. The full schema (T014–T022) is foundational because every story needs it.
- **User Stories (Phases 3–12)**: All depend on Foundational completion.
  - **US1** (project/scope) and **US2** (documents/parsing) can start in parallel after Foundational.
  - **US3** (analysis/AI) depends on **US2** (uses `ExtractedFact`s) and **US1** (project + provider).
  - **US4** (review) depends on **US3** (proposal items exist).
  - **US5** (validation/finalize) depends on **US4** (decisions/dataset).
  - **US6** (export) depends on **US5** (validation gate) and **US3** (dataset).
  - **US7** (traceability) depends on **US6**.
  - **US8** (monitor) depends on **US1** but is best after **US4** (counts).
  - **US9** (reopen) depends on **US6** (exported state).
  - **US10** (provider) depends on **US3**.
- **Polish (Phase 13)**: Depends on the desired stories being complete.

### Within Each User Story

- Tests are written first and MUST fail before implementation.
- Models → services → endpoints → integration.
- Each story is independently completable and testable.

### Parallel Opportunities

- Setup: T002–T007 run in parallel after T001.
- Foundational: T010–T012, T014–T021, T024, T026, T028–T031 offer parallelism; T022 (migration) depends on T014–T021.
- US2: T041–T049 (storage, schemas, extractors) run in parallel; T050–T052 depend on them.
- US3: T058–T063 (schemas, Protocol, prompts, fake, providers) run in parallel; T066–T068 steps run in parallel; T070 orchestrator depends on all steps.
- US6: T092–T096 generators run in parallel; T097 depends on them.

---

## Parallel Example: User Story 3

```bash
# Launch AI-layer tasks together:
Task: "Implement AI schemas in src/workshop/ai/schemas.py"
Task: "Define AIClient Protocol in src/workshop/ai/client.py"
Task: "Implement prompts in src/workshop/ai/prompts.py"
Task: "Implement FakeAIClient in src/workshop/ai/fake.py"
Task: "Implement LocalQwenClient in src/workshop/ai/providers/local_qwen_client.py"

# Launch detection steps together:
Task: "Implement detect-conflicts.step in src/workshop/analysis/steps/detect_conflicts.py"
Task: "Implement detect-duplicates.step in src/workshop/analysis/steps/detect_duplicates.py"
Task: "Implement recommend-mapping.step in src/workshop/analysis/steps/recommend_mapping.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1) — a consultant can create and scope a project.
3. **STOP and VALIDATE**: run US1 tests independently.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → validate. 3. US2 → validate. 4. US3 → validate. 5. US4 → validate. 6. US5 → validate. 7. US6 → validate (full P1 flow end-to-end).
8. US7–US10 in priority order.
9. Polish.

### Parallel Team Strategy

After Foundational: Developer A takes US1 + US8; Developer B takes US2; then US3 (A+B), then US4→US5→US6 in sequence (single critical path), with US9/US10/US7 in parallel once their dependencies land.

---

## Notes

- [P] = different files, no dependencies.
- The critical path is Setup → Foundational → US2 → US3 → US4 → US5 → US6.
- Write tests first and confirm they fail; commit after each task or logical group.
- Independent test criteria per story:
  - US1: create/scope/transition with guards.
  - US2: version/supersede + source-referenced parsing.
  - US3: proposal round with flags; AI failure fails the run with no partial proposal.
  - US4: decisions insert-only; locking + re-proposal.
  - US5: finalization blocked until resolved + all rules pass.
  - US6: exact template package, versioned, all-or-nothing.
  - US7: value → source + approving decision.
  - US8: overview counts for monitors.
  - US9: reopen logged; new package version, prior intact.
  - US10: provider-independent behavior.
