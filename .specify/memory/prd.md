# System Architecture: Workshop Module

**Author**: Principal Software Architect
**Status**: Draft v1.0
**Scope**: Architecture for the Workshop Module inside the existing HRMS SaaS platform
**Design objective**: Correctness, maintainability, simplicity — **not** scalability

---

## 0. Architectural Philosophy

Before any diagram, the governing rule for every decision below:

> **This system runs a few times a year, per customer, with a human in the loop at every important step. It is a document-to-structured-data conversion and approval tool, not a real-time or high-throughput system.**

Consequences of that framing:

- **One new module inside the existing NestJS monolith**, not a new service. No new deployable unit unless something has a genuinely different scaling/security/runtime profile (only the AI call-out does — see §17).
- **No event sourcing, no CQRS, no workflow engine.** The "workflow" is 6 fixed statuses on a single row — a state machine implemented as an enum + guard functions, not a framework.
- **Kafka is used, but only where the platform already uses it** — for cross-module domain events the rest of the HRMS platform listens to (e.g., "workshop exported"). It is *not* used to sequence internal Workshop Module logic. Internal steps are plain synchronous/async NestJS service calls or, at most, a single BullMQ (Redis-backed) job queue for long-running AI/parsing work.
- **AI is a single request/response service behind one interface (`AIClient`).** No agents, no multi-agent orchestration, no LangGraph/CrewAI/AutoGen. The "intelligence" is prompt + schema + deterministic post-processing, not an autonomous loop.
- **Deterministic code does everything it can**: parsing, diffing, validation, Excel generation, referential integrity checks. AI is invoked **only** for the steps that genuinely require semantic judgment: reading unstructured documents into candidate facts, proposing mappings/normalization, and writing plain-language explanations.
- **Reuse, don't build**: OCR, PDF/Excel parsing, and validation all come from mature open-source libraries (§18). Engineering effort goes into the orchestration and traceability model, which is the actual business value.

---

## 1. Overall Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Existing HRMS SaaS Platform                  │
│                                                                        │
│   ┌───────────────────────────────────────────────────────────────┐  │
│   │                     NestJS Monolith (API)                     │  │
│   │                                                                 │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │  │
│   │  │  Core HRMS  │  │   Auth /    │  │   Workshop Module    │    │  │
│   │  │  Modules    │  │   Tenancy   │  │   (new, this doc)    │    │  │
│   │  │ (existing)  │  │  (existing) │  │                       │    │  │
│   │  └─────────────┘  └─────────────┘  └──────────┬────────────┘    │  │
│   │                                                 │                 │  │
│   └─────────────────────────────────────────────────┼─────────────────┘  │
│                                                       │                   │
│         ┌──────────────┬──────────────┬──────────────┼──────────┐        │
│         ▼              ▼              ▼              ▼          ▼        │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ ┌────────┐  │
│   │ PostgreSQL│  │   Redis   │  │  S3/MinIO │  │   Kafka   │ │AIClient│  │
│   │ (workshop │  │ (BullMQ   │  │ (documents│  │ (domain   │ │(OpenAI │  │
│   │  schema)  │  │  job queue│  │  exports) │  │  events   │ │ or     │  │
│   │           │  │  + cache) │  │           │  │  out)     │ │ Qwen)  │  │
│   └───────────┘  └───────────┘  └───────────┘  └───────────┘ └────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

Key points:
- **One codebase, one deployable API service** (existing NestJS app), extended with a new `workshop` module/domain.
- **One database, one schema namespace** (`workshop_*` tables) inside the existing PostgreSQL instance/cluster — not a separate database. Simplifies backup, migration, and joins against existing tenant/customer tables.
- **Redis** is reused for exactly one purpose here: a job queue (BullMQ) for Analysis Runs, which can take minutes (OCR + AI calls) and must not block HTTP requests.
- **Kafka** is reused for exactly one purpose here: publishing coarse-grained domain events (`workshop.exported`, `workshop.finalized`) that other existing platform modules may already subscribe to (e.g., billing, notifications). The Workshop Module does not consume Kafka internally to drive its own logic.
- **S3/MinIO** stores raw uploaded documents and generated export packages. Nothing else.
- **AIClient** is an outbound HTTP call to either OpenAI or a self-hosted Qwen endpoint, abstracted so the rest of the system is provider-agnostic.

---

## 2. Module Decomposition

Inside the NestJS monolith, the Workshop Module is one **domain module** (`WorkshopModule`) composed of **cohesive sub-modules**, each with a single responsibility. No sub-module is a separately deployed service.

| Sub-module | Responsibility |
|---|---|
| `workshop-project` | CRUD + lifecycle state machine for Workshop Projects |
| `workshop-document` | Upload, versioning, tagging, storage pointer management |
| `workshop-parsing` | Deterministic extraction of raw text/tables/cells from PDFs, Word, Excel, images (OCR) — no AI |
| `workshop-ai` | The `AIClient` interface, provider adapters, prompt templates, response schema validation |
| `workshop-analysis` | Orchestrates one Analysis Run: parsing → AI → structured Proposal (this is the "Workshop Agent") |
| `workshop-proposal` | Proposal / Proposal Item storage, round numbering, round comparison |
| `workshop-review` | Accept / Reject / Modify actions, Decision recording, item-state tracking |
| `workshop-validation` | Deterministic rule engine run before finalization |
| `workshop-export` | Excel generation, Difference Report, Validation Report, Decision Log, packaging |
| `workshop-audit` | Cross-cutting audit log writer/reader used by all of the above |

All sub-modules live under one NestJS `WorkshopModule` and share the same Postgres schema. They communicate via **direct service injection** (standard NestJS DI) — not via internal events or queues, except where a task must be async (Analysis Run → BullMQ job).

---

## 3. Folder Structure

```
apps/api/src/modules/workshop/
├── workshop.module.ts
├── common/
│   ├── enums/
│   │   ├── project-status.enum.ts
│   │   ├── document-status.enum.ts
│   │   ├── decision-action.enum.ts
│   │   └── entity-type.enum.ts
│   ├── guards/
│   │   └── workshop-permission.guard.ts
│   └── interfaces/
│       └── ai-client.interface.ts
│
├── project/
│   ├── project.controller.ts
│   ├── project.service.ts
│   ├── project.entity.ts
│   ├── project-status.state-machine.ts
│   └── dto/
│
├── document/
│   ├── document.controller.ts
│   ├── document.service.ts
│   ├── document.entity.ts
│   ├── document-version.entity.ts
│   ├── storage/
│   │   └── s3-document-storage.adapter.ts
│   └── dto/
│
├── parsing/
│   ├── parsing.service.ts
│   ├── extractors/
│   │   ├── pdf-extractor.ts        (pdf-parse / pdf.js)
│   │   ├── docx-extractor.ts       (mammoth)
│   │   ├── xlsx-extractor.ts       (exceljs / SheetJS)
│   │   ├── image-ocr-extractor.ts  (Tesseract.js or cloud OCR)
│   │   └── extractor.interface.ts
│   └── models/
│       └── extracted-fact.model.ts
│
├── ai/
│   ├── ai-client.interface.ts
│   ├── ai-client.factory.ts
│   ├── providers/
│   │   ├── openai.ai-client.ts
│   │   └── local-qwen.ai-client.ts
│   ├── prompts/
│   │   ├── extraction.prompt.ts
│   │   ├── mapping.prompt.ts
│   │   ├── conflict-detection.prompt.ts
│   │   └── explanation.prompt.ts
│   └── schemas/
│       └── ai-response.schema.ts   (zod schemas — validated on every AI response)
│
├── analysis/
│   ├── analysis-run.controller.ts
│   ├── analysis-run.service.ts     ("Workshop Agent" orchestrator)
│   ├── analysis-run.entity.ts
│   ├── analysis.processor.ts       (BullMQ worker)
│   └── steps/
│       ├── extract-facts.step.ts
│       ├── detect-conflicts.step.ts
│       ├── detect-duplicates.step.ts
│       ├── recommend-mapping.step.ts
│       └── build-proposal.step.ts
│
├── proposal/
│   ├── proposal.controller.ts
│   ├── proposal.service.ts
│   ├── proposal.entity.ts
│   ├── proposal-item.entity.ts
│   └── round-comparison.service.ts
│
├── review/
│   ├── review.controller.ts
│   ├── review.service.ts
│   └── decision.entity.ts
│
├── validation/
│   ├── validation.controller.ts
│   ├── validation.service.ts
│   ├── rules/
│   │   ├── referential-integrity.rule.ts
│   │   ├── duplicate-identifier.rule.ts
│   │   ├── orphaned-entity.rule.ts
│   │   ├── unresolved-conflict.rule.ts
│   │   └── unresolved-assumption.rule.ts
│   └── rule.interface.ts
│
├── export/
│   ├── export.controller.ts
│   ├── export.service.ts
│   ├── generators/
│   │   ├── excel-package.generator.ts   (exceljs)
│   │   ├── difference-report.generator.ts
│   │   ├── validation-report.generator.ts
│   │   └── decision-log.generator.ts
│   └── export-package.entity.ts
│
└── audit/
    ├── audit.service.ts
    └── audit-log.entity.ts
```

This mirrors the ten functional areas from the PRD 1:1 — each sub-folder is independently testable and has one reason to change.

---

## 4. Database Design

Single PostgreSQL schema, `workshop`. All tables are **append-friendly / versioned**, never destructively updated for anything that has been shown to a user (consistent with FR-7.x, immutability of rounds).

### Core tables

```sql
-- Project
workshop_project (
  id UUID PK,
  tenant_id UUID NOT NULL,          -- existing platform tenancy
  customer_id UUID NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,             -- enum: Setup..Exported
  ai_provider TEXT NOT NULL,        -- 'OPENAI' | 'LOCAL_QWEN'
  scoped_entity_types TEXT[] NOT NULL,
  current_round INT NOT NULL DEFAULT 0,
  created_by UUID, created_at TIMESTAMPTZ,
  archived_at TIMESTAMPTZ NULL
)

-- Documents
workshop_document (
  id UUID PK,
  project_id UUID FK -> workshop_project,
  document_type TEXT NOT NULL,
  status TEXT NOT NULL,             -- Uploaded | Analyzed | Superseded
  current_version_id UUID FK -> workshop_document_version,
  notes TEXT,
  created_by UUID, created_at TIMESTAMPTZ
)

workshop_document_version (
  id UUID PK,
  document_id UUID FK -> workshop_document,
  version_number INT NOT NULL,
  storage_key TEXT NOT NULL,        -- S3/MinIO object key
  file_name TEXT, mime_type TEXT, checksum TEXT,
  uploaded_by UUID, uploaded_at TIMESTAMPTZ,
  superseded_at TIMESTAMPTZ NULL
)

-- Analysis Runs (async jobs)
workshop_analysis_run (
  id UUID PK,
  project_id UUID FK -> workshop_project,
  round_number INT NOT NULL,
  status TEXT NOT NULL,             -- Queued | Running | Completed | Failed
  ai_provider TEXT NOT NULL,
  document_version_ids UUID[] NOT NULL,   -- exact input snapshot
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  error_message TEXT NULL,
  triggered_by UUID
)

-- Proposals (one per completed Analysis Run)
workshop_proposal (
  id UUID PK,
  project_id UUID FK -> workshop_project,
  analysis_run_id UUID FK -> workshop_analysis_run,
  round_number INT NOT NULL,
  created_at TIMESTAMPTZ,
  UNIQUE(project_id, round_number)
)

workshop_proposal_item (
  id UUID PK,
  proposal_id UUID FK -> workshop_proposal,
  entity_type TEXT NOT NULL,         -- Company | Location | Department | ...
  entity_key TEXT NOT NULL,          -- stable logical key across rounds (see §13)
  proposed_value JSONB NOT NULL,
  explanation TEXT NOT NULL,
  confidence TEXT NOT NULL,          -- High | Medium | Low
  is_assumption BOOLEAN DEFAULT FALSE,
  has_conflict BOOLEAN DEFAULT FALSE,
  conflict_alternatives JSONB NULL,  -- [{value, sourceDocRef}, ...]
  source_refs JSONB NOT NULL,        -- [{documentVersionId, page/sheet, cell/row}]
  carried_from_item_id UUID NULL     -- FK to prior round's item, if locked/unchanged
)

-- Decisions (human actions — never overwritten)
workshop_decision (
  id UUID PK,
  proposal_item_id UUID FK -> workshop_proposal_item,
  action TEXT NOT NULL,              -- Accept | Reject | Modify
  resulting_value JSONB NOT NULL,
  comment TEXT NULL,
  decided_by UUID NOT NULL,
  decided_at TIMESTAMPTZ NOT NULL,
  reopened BOOLEAN DEFAULT FALSE
)

-- Validation
workshop_validation_run (
  id UUID PK,
  project_id UUID FK -> workshop_project,
  triggered_at TIMESTAMPTZ,
  overall_result TEXT NOT NULL       -- Pass | Fail
)

workshop_validation_result (
  id UUID PK,
  validation_run_id UUID FK -> workshop_validation_run,
  rule_code TEXT NOT NULL,
  result TEXT NOT NULL,              -- Pass | Fail
  failing_records JSONB NULL
)

-- Export
workshop_export_package (
  id UUID PK,
  project_id UUID FK -> workshop_project,
  version_number INT NOT NULL,
  storage_prefix TEXT NOT NULL,      -- S3/MinIO folder containing all output files
  exported_by UUID, exported_at TIMESTAMPTZ,
  UNIQUE(project_id, version_number)
)

-- Audit (cross-cutting, append-only)
workshop_audit_log (
  id UUID PK,
  project_id UUID,
  actor_id UUID,
  action TEXT NOT NULL,
  entity_type TEXT, entity_id UUID,
  payload JSONB,
  occurred_at TIMESTAMPTZ NOT NULL
)
```

Design notes:
- `JSONB` is used deliberately for `proposed_value`, `source_refs`, `conflict_alternatives`: the shape varies per entity type (a Company vs. a Reporting Line have different fields), and this is not queried at high volume, so a rigid relational schema per entity type would add complexity without benefit (YAGNI).
- No table is ever `UPDATE`d for historical rows once a Decision or Proposal exists — new rows are inserted instead (see §13, Versioning).
- No table partitioning, no read replicas, no sharding — data volume is small (a handful of workshops per customer per year).

---

## 5. Entity Relationships (ERD, simplified)

```
workshop_project 1───* workshop_document 1───* workshop_document_version
        │
        1───* workshop_analysis_run 1───1 workshop_proposal 1───* workshop_proposal_item
        │                                                              │
        │                                                              1
        │                                                              │
        │                                                              *
        │                                                    workshop_decision
        │
        1───* workshop_validation_run 1───* workshop_validation_result
        │
        1───* workshop_export_package
        │
        1───* workshop_audit_log
```

- A `Project` scopes everything.
- A `Document` has many `DocumentVersion`s (append-only versioning).
- An `AnalysisRun` produces exactly one `Proposal`, which has many `ProposalItem`s.
- Each `ProposalItem` accumulates zero-or-more `Decision`s over time (normally one, but reopening can add more — see §13).
- `entity_key` on `ProposalItem` is the stable identifier that lets the UI say "this is the same logical Department across Round 1, 2, 3" even though each round's item is a new row.

---

## 6. Workshop Lifecycle

Implemented as a plain enum + explicit guard functions — **not** a workflow engine.

```
Setup ──▶ Collecting Documents ──▶ In Analysis ──▶ In Review ──▶ Finalized ──▶ Exported
                                        ▲                │
                                        └────────────────┘
                                  (new Analysis Round triggered)
```

```ts
// project-status.state-machine.ts
const ALLOWED_TRANSITIONS: Record<ProjectStatus, ProjectStatus[]> = {
  Setup:               ['Collecting Documents'],
  'Collecting Documents': ['In Analysis'],
  'In Analysis':        ['In Review'],
  'In Review':          ['In Analysis', 'Finalized'],   // back-edge for new rounds
  Finalized:            ['Exported'],
  Exported:             ['In Review'],                   // explicit reopen only
};

function assertTransition(from: ProjectStatus, to: ProjectStatus) {
  if (!ALLOWED_TRANSITIONS[from]?.includes(to)) {
    throw new InvalidTransitionError(from, to);
  }
}
```

Guard conditions enforced at the service layer, not the DB layer:
- `In Review → Finalized` requires FR-5.7 (no Pending/Rejected items) **and** last `workshop_validation_run.overall_result = Pass`.
- `Exported → In Review` (reopen) writes an `workshop_audit_log` entry and increments a reopen counter used to version future exports (FR-6.4, FR-9.6).

This is intentionally the simplest possible implementation of "workflow": a lookup table and a guard function. A workflow engine (Temporal, etc.) would add operational complexity (extra service, extra failure mode) for a 6-state, low-frequency, single-tenant-at-a-time process — explicitly rejected per constraints.

---

## 7. AI Interaction Flow

The **Workshop Agent** (`analysis-run.service.ts`) is a deterministic orchestrator that calls AI at specific, narrow points. It is not an autonomous agent with tool loops.

```
1. Load active (non-Superseded) DocumentVersions in scope
2. Deterministically parse each into ExtractedFact[] (workshop-parsing, no AI)
3. For each in-scope entity type:
     a. Call AIClient.extractFacts(entityType, extractedFacts, priorDecisions)
     b. Validate AI response against zod schema (workshop-ai/schemas)
     c. If schema invalid → retry once → else mark AnalysisRun Failed (never silently proceed)
4. Deterministically merge AI output with priorDecisions:
     - locked (Accepted/Modified) items are NOT re-sent to AI, carried forward as-is
     - only Pending/Rejected/new items go through steps 4a-4c
5. Deterministically detect duplicates (string similarity / rule-based first pass)
   → optionally confirmed by one AI call for ambiguous cases only
6. Deterministically detect conflicts (same entity_key, different proposed_value
   across documents) — this is set comparison, not AI
7. For each item requiring explanation, call AIClient.explain(item) for
   plain-language text (or reuse explanation returned in step 3 if already present)
8. Persist Proposal + ProposalItems in one transaction
9. Mark AnalysisRun Completed; project status → In Review
```

Key point: **conflict detection and duplicate detection are primarily deterministic** (string/structural comparison), per the "prefer deterministic code over AI" constraint. AI is used for (a) reading unstructured documents into structured candidate facts, and (b) producing human-readable explanations and semantic mapping recommendations (e.g., "Business Unit" → "Department") — the two tasks that genuinely require language understanding.

---

## 8. Document Parsing Pipeline

Fully deterministic, no AI, one extractor per format, unified output model:

```
DocumentVersion (S3 object)
        │
        ▼
 ┌─────────────────────────────┐
 │ ExtractorFactory.get(mime)  │
 └──────────────┬───────────────┘
                ▼
   ┌───────────┬───────────┬────────────┬─────────────┐
   │ PDF        │ DOCX       │ XLSX/CSV   │ Image (scan)│
   │ pdf-parse  │ mammoth    │ exceljs /  │ Tesseract.js│
   │ / pdf.js   │            │ papaparse  │ or cloud OCR│
   └───────────┴───────────┴────────────┴─────────────┘
                ▼
      ExtractedFact[] { text, page/sheet, row/cell, bbox? }
                ▼
      Stored transiently (Redis or scratch table) for the
      duration of the Analysis Run, referenced by source_refs
      in the resulting ProposalItems
```

- Extractors implement one shared `Extractor` interface (`extract(buffer): ExtractedFact[]`) so `workshop-analysis` never branches on file type.
- OCR output includes a per-field confidence from the OCR engine itself, which is folded into the AI's own confidence scoring as a lower bound (a low-confidence OCR read cannot become a High-confidence proposal).
- Raw parsed text is **not** persisted long-term as its own entity — it exists only to (a) build `ExtractedFact`s referenced by `source_refs`, and (b) feed the AI prompt. This avoids building a redundant "parsed document" data model (YAGNI).

---

## 9. Proposal Generation Flow

```
Trigger Analysis Run (consultant action)
        │
        ▼
  Enqueue BullMQ job (workshop-analysis queue)
        │
        ▼  (async worker, off the HTTP request path)
  analysis.processor.ts
        │
        ├─ Steps 1-9 from §7
        │
        ▼
  Proposal (Round N) + ProposalItems persisted
        │
        ▼
  Project status: In Analysis → In Review
        │
        ▼
  Notify consultant/customer (existing notification module, via Kafka event
  `workshop.proposal.ready` if the platform's notification system already
  subscribes to Kafka; otherwise a direct in-app notification call)
```

Why async/queued rather than synchronous HTTP: AI + OCR calls can take from seconds to a few minutes. A queue avoids HTTP timeouts and lets the consultant navigate away and come back — appropriate given performance is explicitly not a priority, but a blocking multi-minute HTTP call would be poor UX regardless of scale.

---

## 10. Validation Flow

```
Trigger (auto, when last item transitions to Accepted/Modified,
         OR manual re-run during In Review)
        │
        ▼
 ValidationService.run(projectId)
        │
        ├─ Load "current accepted dataset" view (see §13)
        ├─ For each rule in RuleRegistry (referential integrity,
        │   duplicate identifiers, orphaned entities, unresolved
        │   conflicts, unresolved assumptions):
        │     rule.evaluate(dataset) → { pass, failingRecords[] }
        ├─ Persist workshop_validation_run + workshop_validation_result rows
        │
        ▼
 overall_result = Pass only if every rule passes
        │
        ▼
 Project can transition to Finalized only if overall_result = Pass
```

Rules are plain synchronous TypeScript functions implementing one `ValidationRule` interface — no external rule engine (e.g., no JSON-logic/Drools). Given the fixed, small rule set (5 rules today), a rule engine would be an unjustified abstraction (YAGNI). Adding a rule = adding one file + one registry entry.

---

## 11. Review Flow

```
Reviewer opens Proposal Round N (via workshop-proposal read APIs)
        │
        ▼
For each ProposalItem, reviewer submits one action:
        │
   ┌────┴─────┬──────────┐
   ▼          ▼          ▼
 Accept    Reject     Modify
   │          │          │
   └────┬─────┴────┬─────┘
        ▼           
 ReviewService.recordDecision(itemId, action, value, comment, userId)
        │
        ├─ INSERT workshop_decision (never update existing decisions)
        ├─ INSERT workshop_audit_log
        ├─ Recompute project's open-item counters (FR-1.4/5.6) — simple
        │   COUNT query, no cached aggregate needed at this volume
        │
        ▼
 If item was Rejected: stays open, must appear in next Analysis Run's
   "Pending/Rejected" input set (§7 step 4)
 If item was Accepted/Modified: locked; carried forward unchanged in
   all future rounds via carried_from_item_id
```

Both consultant and customer users call the same API; `decided_by` plus the existing platform's user/role model (§14-15) distinguishes who acted.

---

## 12. Export Flow

```
Project status = Finalized, user triggers Export
        │
        ▼
 ExportService.generate(projectId)
        │
        ├─ Build "final accepted dataset" (§13) from latest Decisions
        ├─ excel-package.generator.ts  → Companies.xlsx ... ApprovalWorkflows.xlsx
        │     (using existing HRMS standard import template as the target schema)
        ├─ difference-report.generator.ts → final value vs. original source value,
        │     per item, using source_refs + is_assumption flags
        ├─ validation-report.generator.ts → last passing workshop_validation_run
        ├─ decision-log.generator.ts → all workshop_decision rows, chronological
        │
        ▼
 Upload all files to S3/MinIO under a new versioned prefix:
   s3://workshop/{projectId}/exports/v{n}/...
        │
        ▼
 INSERT workshop_export_package (version_number = n)
        │
        ▼
 Project status → Exported
        │
        ▼
 Publish Kafka event `workshop.exported` (payload: projectId, packageVersion,
   S3 prefix) for any existing downstream platform module (e.g., the
   separate, existing HRMS import tool) to pick up — Workshop Module does
   not perform the import itself (explicit non-goal).
```

---

## 13. Versioning Strategy

Two distinct versioning concerns, both handled by **insert-only tables**, no event sourcing/CQRS framework:

**a) Document versioning** — `workshop_document_version`, one row per upload, `document.current_version_id` pointer moves forward. Old versions never deleted, only the parent `document.status` becomes `Superseded` (or a specific version is excluded from future analysis via a boolean, if partial supersession is ever needed — not needed today, so not built).

**b) Proposal/dataset versioning** — every `workshop_proposal` (one per round) is immutable once created. The "current accepted dataset" used by Validation and Export is **not** a separately stored table; it is a **derived read model**, computed on demand as:

```sql
-- Conceptual: latest decision per entity_key that is Accept/Modify,
-- scoped to the highest round number in which that entity_key appears.
SELECT DISTINCT ON (pi.entity_key)
       pi.entity_key, pi.entity_type, d.resulting_value, d.decided_by, d.decided_at,
       pi.source_refs, pi.is_assumption
FROM workshop_proposal_item pi
JOIN workshop_decision d ON d.proposal_item_id = pi.id
JOIN workshop_proposal p ON p.id = pi.proposal_id
WHERE p.project_id = :projectId
  AND d.action IN ('Accept', 'Modify')
ORDER BY pi.entity_key, p.round_number DESC, d.decided_at DESC;
```

This single query (indexed on `entity_key`, `project_id`) is the entire "versioning engine." Given workshop data volumes (hundreds to low thousands of items per project, a handful of rounds), this is fast enough with a plain B-tree index — no materialized view or snapshot table required (YAGNI). If profiling ever shows otherwise, a materialized view can be added later without changing the write model — but it is not built speculatively.

The **Final export snapshot** (FR-7.3) is simply the result of this query captured into the generated Excel files at export time — the files themselves *are* the immutable "Final" snapshot, stored in S3 under a versioned prefix (§12). No separate "final dataset" table is needed.

---

## 14. Security Model

- **Reuses the existing HRMS platform's authentication** (existing session/JWT mechanism) — no new auth system.
- **Tenant isolation**: every table carries `project_id → tenant_id` and all queries go through a `tenant_id` filter enforced at the repository layer (consistent with however the existing platform enforces multi-tenancy — likely a NestJS interceptor/guard already in place, reused as-is).
- **Document storage isolation**: S3/MinIO keys are namespaced `tenant/{tenantId}/workshop/{projectId}/...`; bucket policy denies cross-tenant key access; signed URLs (short TTL) are used for upload/download rather than exposing permanent public links.
- **AI provider calls**: outbound calls to OpenAI or the self-hosted Qwen endpoint carry no more data than the specific extraction/explanation task requires; no full-document dumps beyond what's needed for that entity type's extraction. Local Qwen is preferred by any customer with data-residency requirements (that's the reason the per-project `ai_provider` switch exists at all — not a hypothetical, it's a real compliance requirement, hence it's in scope; a full pluggable-provider *marketplace* would not be, per YAGNI).
- **Secrets** (OpenAI API key, Qwen endpoint credentials) stored in the existing platform's secret manager / Kubernetes Secrets — not in the `workshop_project` table (only the provider *choice* is stored there, never credentials).

---

## 15. Permission Model

Reuses the existing platform's RBAC (roles/permissions already modeled for the HRMS system); Workshop Module adds a small number of module-specific permissions checked via a single `WorkshopPermissionGuard`:

| Permission | Consultant | Customer Reviewer | Project Manager | Admin |
|---|---|---|---|---|
| Create/configure project | ✔ | ✘ | ✘ | ✔ |
| Upload documents | ✔ | ✔ | ✘ | ✔ |
| Trigger Analysis Run | ✔ | ✘ | ✘ | ✔ |
| Review (Accept/Reject/Modify) | ✔ | ✔ | ✘ | ✔ |
| View project status/progress | ✔ | ✔ | ✔ | ✔ |
| Finalize project | ✔ | ✘ | ✘ | ✔ |
| Export package | ✔ | ✘ | ✘ | ✔ |
| Reopen exported project | ✔ (with confirmation) | ✘ | ✘ | ✔ |

Access to a given project additionally requires an explicit **project membership** row (`workshop_project_member(project_id, user_id, role)`) — a consultant or customer user only sees projects they're assigned to, independent of their global platform role. This is the one new, genuinely necessary permission concept (project-scoped access on top of platform RBAC); no separate permission *engine* is built.

---

## 16. Object Storage Strategy

Single bucket (or bucket-per-environment, matching existing platform convention), key structure:

```
workshop/{tenantId}/{projectId}/documents/{documentId}/{versionId}/{originalFileName}
workshop/{tenantId}/{projectId}/exports/v{n}/Companies.xlsx
workshop/{tenantId}/{projectId}/exports/v{n}/DifferenceReport.xlsx
workshop/{tenantId}/{projectId}/exports/v{n}/ValidationReport.xlsx
workshop/{tenantId}/{projectId}/exports/v{n}/DecisionLog.xlsx
```

- Uploads: client requests a pre-signed PUT URL from `workshop-document` API, uploads directly to S3/MinIO (avoids proxying large files through the NestJS API).
- Downloads (exports): pre-signed GET URLs, short TTL.
- No lifecycle deletion rules — documents and exports are retained indefinitely for audit (FR-9.5, "permanent record"), consistent with the "never delete, only supersede/version" principle. Storage cost is a non-issue given workshop frequency.
- No separate blob-metadata service — S3 object keys plus the Postgres `workshop_document_version.storage_key` column are the only source of truth for locating a file.

---

## 17. AIClient Abstraction

This is the one place a strict interface boundary matters, because the AI Processing Policy explicitly requires the Workshop Agent to be provider-agnostic.

```ts
// ai-client.interface.ts
export interface AIClient {
  extractFacts(input: ExtractFactsRequest): Promise<ExtractFactsResponse>;
  recommendMapping(input: MappingRequest): Promise<MappingResponse>;
  explain(input: ExplainRequest): Promise<ExplainResponse>;
}

export interface ExtractFactsRequest {
  entityType: EntityType;
  extractedFacts: ExtractedFact[];
  priorAcceptedContext: ProposalItemSummary[]; // locked decisions, for consistency
}

export interface ExtractFactsResponse {
  items: {
    entityKey: string;
    proposedValue: Record<string, unknown>;
    confidence: 'High' | 'Medium' | 'Low';
    isAssumption: boolean;
    explanation: string;
    sourceRefs: SourceRef[];
  }[];
}
```

```ts
// ai-client.factory.ts
@Injectable()
export class AIClientFactory {
  constructor(
    private readonly openAiClient: OpenAiAIClient,
    private readonly qwenClient: LocalQwenAIClient,
  ) {}

  forProject(project: WorkshopProject): AIClient {
    switch (project.aiProvider) {
      case 'OPENAI': return this.openAiClient;
      case 'LOCAL_QWEN': return this.qwenClient;
      default: throw new UnsupportedAIProviderError(project.aiProvider);
    }
  }
}
```

- `analysis-run.service.ts` (the Workshop Agent) depends **only** on the `AIClient` interface, resolved once per run via `AIClientFactory.forProject(project)`. It has zero knowledge of OpenAI- or Qwen-specific request/response formats.
- Each provider adapter (`openai.ai-client.ts`, `local-qwen.ai-client.ts`) is responsible for: building the provider-specific request, calling the endpoint, and **mapping the raw response into the shared response types**, validated against the zod schemas in `workshop-ai/schemas` before returning. If a provider's raw output doesn't fit the schema, the adapter throws — the orchestrator never has to guard against provider-specific shapes.
- Both adapters implement retry-with-backoff and timeout handling identically (shared base class or utility), so provider swapping never changes error-handling behavior.
- Prompts live in `workshop-ai/prompts` as plain template functions returning strings — no prompt-management framework, since prompts are versioned in source control like any other code (sufficient for a system used a few times a year).

---

## 18. Open Source Libraries (Reuse, Don't Reinvent)

| Concern | Library | Notes |
|---|---|---|
| PDF text extraction | `pdf-parse` (or `pdfjs-dist` for layout-aware needs) | Mature, widely used in Node |
| Word (.docx) extraction | `mammoth` | Converts docx to text/HTML reliably |
| Excel/CSV parsing & generation | `exceljs` | Both reading source files and generating the final `.xlsx` import package |
| CSV parsing | `papaparse` | Simple, streaming-capable |
| OCR (scanned documents) | `tesseract.js`, or a cloud OCR API (e.g., AWS Textract) if higher accuracy is required for messy scans | Decision left to a spike; both are "don't reinvent" choices |
| Schema/response validation | `zod` | Validates every AI response and every DTO — one validation library platform-wide |
| Job queue | `bullmq` (Redis-backed, already have Redis) | For async Analysis Runs |
| Excel styling/templates (if the standard import template has fixed formatting) | `exceljs` templating support | Avoids building a custom Excel writer |
| String similarity (duplicate detection) | `string-similarity` or `fastest-levenshtein` | Deterministic first pass before any AI involvement |
| HTTP client for AI providers | Existing platform HTTP client (e.g., `axios`/`got`) wrapped per adapter | No new HTTP layer |

No custom parser, no custom OCR model, no custom AI agent framework is written. Engineering effort is spent entirely on orchestration, data modeling, and traceability — the part that is actually specific to this business problem.

---

## 19. Error Handling

Principles: **fail loud, never silently degrade correctness.**

| Failure | Handling |
|---|---|
| Document parsing fails (corrupt file, unsupported format) | Document marked with a parse-error flag; excluded from that Analysis Run; visible to the user with a clear message; does not fail the whole run unless it's the only document |
| AI call fails (timeout, 5xx) | Retry once with backoff; if still failing, `AnalysisRun.status = Failed`, `error_message` populated, project stays in `In Analysis`, user can retry manually — **no partial/silent Proposal is ever created** |
| AI response fails schema validation (`zod`) | Treated identically to an AI failure — never coerced into a "best guess" shape. This is a hard rule: malformed AI output must never become a ProposalItem. |
| Validation rule throws (bug, not a rule failure) | Whole Validation Run marked `Fail` with the exception captured in `failing_records`; project cannot finalize — errs toward blocking, not toward false positives |
| Export generation fails partway | Entire export package generation runs in one transaction/temp-directory; nothing is uploaded to S3 and no `workshop_export_package` row is created unless **all** files generate successfully — no partial packages |
| Concurrent review actions on the same item | Last-write-wins is *not* acceptable here (traceability). `workshop_decision` is insert-only, so concurrent submissions simply create two decision rows; the UI treats the item as needing reconciliation if more than one decision exists without a clear latest-wins timestamp ordering — surfaced to the consultant rather than auto-resolved |

All errors surfaced to the API layer via standard NestJS exception filters, mapped to clear HTTP error codes + human-readable messages (no raw stack traces to the client).

---

## 20. Logging and Auditing

Two distinct layers, deliberately kept separate:

**a) Operational logging** (existing platform convention — e.g., structured JSON logs via the platform's existing logger, shipped to whatever the platform already uses). Used for debugging, not for business audit. Not retained specially.

**b) Business audit trail** (`workshop_audit_log`) — this is a **first-class, permanent, queryable business record**, not just log lines. Every state-changing action writes one row:

- Document uploaded / superseded
- Analysis Run triggered / completed / failed
- Proposal generated
- Decision recorded (Accept/Reject/Modify)
- Validation run + result
- Project status transition
- Export generated
- Project reopened

This table is what makes FR-7 ("full auditability") and NFR-9.3 concrete: it is queried directly to answer "who did what, when" for any project, and is included conceptually in the Decision Log export (§12). It is deliberately a simple append-only table with a `payload JSONB` column — not a generic event-sourcing store used to *reconstruct* state (state is reconstructed from the domain tables in §4-5; the audit log is a **read-oriented record of intent**, not the source of truth for current state). This distinction keeps the system out of full event-sourcing/CQRS territory while still meeting the auditability requirement.

---

## 21. Sequence Diagram — Analysis Run

```
Consultant        API (workshop-analysis)   BullMQ         Workshop Agent      AIClient        Postgres        S3
    │  trigger run       │                     │                  │                 │               │            │
    ├────────────────────▶                     │                  │                 │               │            │
    │                     │  enqueue job        │                  │                 │               │            │
    │                     ├─────────────────────▶                  │                 │               │            │
    │  202 Accepted       │                     │                  │                 │               │            │
    ◀─────────────────────┤                     │                  │                 │               │            │
    │                     │                     │  process job     │                 │               │            │
    │                     │                     ├──────────────────▶                 │               │            │
    │                     │                     │                  │  fetch docs     │               │            │
    │                     │                     │                  ├─────────────────┼───────────────┼───────────▶│
    │                     │                     │                  │  parse (local)  │               │            │
    │                     │                     │                  │  extractFacts() │               │            │
    │                     │                     │                  ├─────────────────▶               │            │
    │                     │                     │                  │  validated resp │               │            │
    │                     │                     │                  ◀─────────────────┤               │            │
    │                     │                     │                  │  merge + persist Proposal        │            │
    │                     │                     │                  ├───────────────────────────────────▶          │
    │                     │                     │  job done        │                 │               │            │
    │                     │                     ◀──────────────────┤                 │               │            │
    │  (poll or push) status = In Review          │                  │                 │               │            │
    ◀──────────────────────────────────────────────                │                 │               │            │
```

---

## 22. Activity Diagram — Review to Finalization

```
       ┌───────────────┐
       │ Open Proposal │
       │    Round N    │
       └───────┬────────┘
               ▼
     ┌───────────────────┐
     │ For each item:     │
     │ Accept/Reject/Modify│
     └─────────┬───────────┘
               ▼
        ┌─────────────┐
        │ All items    │──No──▶ Trigger new Analysis Run (Round N+1) ──┐
        │ resolved?    │                                                │
        └──────┬───────┘                                                │
              Yes                                                       │
               ▼                                                        │
     ┌───────────────────┐                                              │
     │ Run Validation     │◀─────────────────────────────────────────────┘
     └─────────┬───────────┘
               ▼
        ┌─────────────┐
        │ Pass?        │──No──▶ Show failures, stay In Review
        └──────┬───────┘
              Yes
               ▼
     ┌───────────────────┐
     │ Status: Finalized  │
     └─────────┬───────────┘
               ▼
     ┌───────────────────┐
     │ Trigger Export      │
     └─────────┬───────────┘
               ▼
     ┌───────────────────┐
     │ Status: Exported    │
     └───────────────────┘
```

---

## 23. Class Diagram (Core Domain, simplified)

```
┌────────────────────┐        ┌───────────────────────┐
│ WorkshopProject     │        │ WorkshopDocument       │
├────────────────────┤        ├───────────────────────┤
│ id                  │1      *│ id                     │
│ tenantId            ├───────▶│ documentType           │
│ status              │        │ status                 │
│ aiProvider          │        │ currentVersionId        │
│ scopedEntityTypes[] │        └───────────┬─────────────┘
│ currentRound        │                    │1
└─────────┬───────────┘                    │*
          │1                    ┌──────────────────────┐
          │*                    │ WorkshopDocumentVersion│
┌────────────────────┐          ├──────────────────────┤
│ WorkshopAnalysisRun │          │ storageKey            │
├────────────────────┤          │ versionNumber         │
│ id                  │          └──────────────────────┘
│ status              │
│ aiProvider          │
└─────────┬───────────┘
          │1
          │1
┌────────────────────┐        ┌───────────────────────┐
│ WorkshopProposal    │1      *│ WorkshopProposalItem   │
├────────────────────┤───────▶├───────────────────────┤
│ roundNumber         │        │ entityType             │
└────────────────────┘        │ entityKey              │
                               │ proposedValue          │
                               │ confidence             │
                               │ isAssumption           │
                               │ hasConflict            │
                               │ sourceRefs[]           │
                               └───────────┬─────────────┘
                                           │1
                                           │*
                               ┌───────────────────────┐
                               │ WorkshopDecision       │
                               ├───────────────────────┤
                               │ action                 │
                               │ resultingValue         │
                               │ decidedBy              │
                               │ decidedAt              │
                               └───────────────────────┘

┌───────────────────────────┐
│ <<interface>> AIClient     │
├───────────────────────────┤
│ extractFacts()             │
│ recommendMapping()         │
│ explain()                  │
└─────────────┬───────────────┘
              △
     ┌────────┴─────────┐
┌───────────────┐  ┌─────────────────────┐
│ OpenAiAIClient │  │ LocalQwenAIClient    │
└───────────────┘  └─────────────────────┘
```

---

## 24. Deployment Diagram

```
                         ┌───────────────────────────────────────┐
                         │           Kubernetes Cluster            │
                         │                                          │
                         │  ┌────────────────────────────────────┐  │
                         │  │  Deployment: hrms-api (existing)    │  │
                         │  │  (includes WorkshopModule — no new  │  │
                         │  │   deployable unit)                  │  │
                         │  │  Pods: N replicas (existing sizing) │  │
                         │  └───────────────┬──────────────────────┘  │
                         │                  │                          │
                         │  ┌───────────────▼───────────────┐          │
                         │  │ Deployment: hrms-worker         │          │
                         │  │ (existing BullMQ worker deploy, │          │
                         │  │  or extend it with a            │          │
                         │  │  `workshop-analysis` queue)     │          │
                         │  └───────────────┬───────────────┘          │
                         │                  │                          │
                         │   ┌──────────────┼───────────────┐          │
                         │   ▼              ▼               ▼          │
                         │ ┌────────┐  ┌──────────┐   ┌───────────┐   │
                         │ │Postgres│  │  Redis   │   │  Kafka    │   │
                         │ │(exist.)│  │ (exist.) │   │ (exist.)  │   │
                         │ └────────┘  └──────────┘   └───────────┘   │
                         │                                          │
                         │   ┌──────────────────────────────────┐  │
                         │   │ (Optional, only if LOCAL_QWEN     │  │
                         │   │  used) Deployment: qwen-inference  │  │
                         │   │  GPU node pool, internal-only svc │  │
                         │   └──────────────────────────────────┘  │
                         └───────────────────┬──────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │  S3 / MinIO         │
                                    │  (existing, or a    │
                                    │  workshop bucket)   │
                                    └────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │  OpenAI API          │
                                    │  (external, via      │
                                    │   egress + secret)   │
                                    └─────────────────────┘
```

- **No new Kubernetes Deployment for the Workshop Module itself** — it ships inside the existing `hrms-api` image/deployment.
- The only genuinely new *infrastructure* consideration is the **optional self-hosted Qwen3.5-27B inference deployment** (GPU node pool), required only for tenants using `LOCAL_QWEN`. This is the one place where a real, justified new component exists — everything else is code inside the existing platform.
- Worker: if the platform already runs a generic BullMQ worker deployment for other async jobs, the Workshop Module simply registers its own queue/processor there rather than getting a dedicated worker deployment (further reducing new infra).

---

## 25. Risk Analysis

| Risk | Impact | Mitigation |
|---|---|---|
| AI returns plausible-but-wrong extracted facts | Incorrect proposal shown to human | Every item requires human Accept/Reject/Modify before it can reach export; nothing is auto-applied; confidence + source_refs make wrong facts easy to spot |
| AI response doesn't match expected schema | Corrupted proposal data | `zod` validation on every AI response; invalid response → Analysis Run fails loudly, never partially persists |
| Local Qwen model quality lower than OpenAI for some document types | Lower confidence / more manual correction | Confidence indicator is provider-agnostic and derived partly from OCR/extraction confidence, not just the LLM's self-reported certainty; customers can be advised on provider choice |
| Large/poorly scanned documents produce poor OCR | Garbage-in extraction | OCR confidence flows into item confidence; very low-confidence items are marked Assumption-like and require explicit human confirmation; fallback to manual entry remains available outside this module |
| Two reviewers submit conflicting decisions on the same item concurrently | Ambiguous "current" decision | Insert-only decision log preserves both; UI/service surfaces the ambiguity rather than silently picking one (§19) |
| BullMQ job lost on worker crash mid-run | Analysis Run stuck in `Running` | BullMQ's built-in retry/stalled-job detection; a stuck run beyond a timeout is marked `Failed` and can be manually retried — acceptable given low run frequency |
| `entity_key` stability across rounds is wrong (two different real-world entities collide, or the same entity gets a new key) | Round comparison and "locked item" logic breaks | `entity_key` generation is deterministic and reviewed as part of `build-proposal.step.ts`; duplicate detection (§7 step 5) exists specifically to catch and let humans merge/split incorrectly keyed entities |
| Scope creep toward configurability (custom rules, custom entity types, workflow customization) | Violates YAGNI, adds long-term maintenance burden | Explicit non-goals in the PRD and this document; any such request should be treated as a new proposal requiring its own justification, not folded in reactively |
| Self-hosted Qwen endpoint unavailable | Analysis Runs fail for LOCAL_QWEN projects | Standard timeout/retry in the adapter; failure surfaces clearly (§19) rather than silently falling back to a different provider (silent provider fallback would break the explicit per-project provider policy) |

---

## 26. Summary

This architecture deliberately contains **one new module, one schema, one queue, one AI interface, and zero new services** beyond an optional GPU inference deployment for self-hosted AI. Every component maps directly to a functional requirement in the PRD; nothing is included "for later." Correctness is protected by insert-only history tables, strict schema validation on AI output, a hard validation gate before finalization, and a permanent audit log — not by architectural sophistication. This is intentional: the business problem is discovery-and-approval at low frequency, and the architecture is sized to match it exactly.