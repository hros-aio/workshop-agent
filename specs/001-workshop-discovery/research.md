# Phase 0 Research: Workshop Module

**Feature**: `001-workshop-discovery`
**Date**: 2026-10-17

The technology stack was fixed by the plan input, the project constitution, and `.specify/memory/tech-stack.md`. There are therefore no open NEEDS CLARIFICATION items in the Technical Context. This document records the decisions, rationale and alternatives for the non-obvious integration points, so implementation tasks can proceed without re-litigating them.

---

## R1. JWT verification and the single authorization dependency

**Decision**: Verify the forwarded platform JWT with PyJWT using either the shared HS256 signing key or the platform JWKS endpoint (RS256), configured via `pydantic-settings`. Extract `sub` (user id), `tenant_id`, and global roles from claims. Implement exactly one FastAPI dependency, `require_project_role(project_id, *roles)`, that (a) validates the token, (b) loads the `workshop_project_member` row for that user and project, (c) checks the requested role, and (d) checks tenant match. All routers depend on it; no endpoint implements its own permission logic.

**Rationale**: The spec (FR-003, FR-004) requires project-scoped membership on top of platform roles. Centralizing this in one dependency matches the constitution's YAGNI/simplicity stance and the tech stack's "one FastAPI dependency for project-membership and role checks".

**Alternatives considered**: A new auth service (rejected — platform already authenticates); per-endpoint inline checks (rejected — drift and missed checks); decoding claims without signature verification behind a trusted proxy (rejected — the service may also be reachable directly via ingress routing).

---

## R2. Arq job model and Analysis Run failure semantics

**Decision**: One Arq job per Analysis Run (`process_analysis_run`), keyed by `analysis_run_id`. The HTTP trigger inserts a `WorkshopAnalysisRun` row with status `Queued`, enqueues the job, and returns `202 Accepted` with the run id. The worker transitions `Queued→Running→Completed|Failed` and records `error_message`. On any AI failure or schema validation failure after one retry, the run is marked `Failed` and **no** `WorkshopProposal` or `WorkshopProposalItem` rows are written. A stuck run past a configurable timeout is reconciled to `Failed` and can be retried manually.

**Rationale**: FR-014 and constitution VIII (Fail Loudly) require atomic, all-or-nothing proposal persistence. OCR + AI calls can take minutes, so an async queue is the correct UX and avoids HTTP timeouts.

**Alternatives considered**: synchronous HTTP (rejected — multi-minute requests); Celery/RQ (rejected — Arq is the stack choice and sufficient); partial proposal persistence with a "draft" state (rejected — violates constitution VIII and FR-014).

---

## R3. Direct-to-object-storage upload with pre-signed URLs

**Decision**: The API creates the logical `WorkshopDocument` + first `WorkshopDocumentVersion` and returns a pre-signed `PUT` URL; the client uploads directly to S3/MinIO and then calls a completion endpoint that verifies the object exists and records checksum/size. Replacement creates a new version, flips `current_version_id`, and marks the previous version superseded. Downloads use short-TTL pre-signed `GET` URLs. Keys follow `workshop/{tenantId}/{projectId}/documents/{documentId}/{versionId}/{filename}`.

**Rationale**: FR-005–FR-008; avoids proxying large files through the API; keeps storage keys namespaced per tenant.

**Alternatives considered**: proxying uploads through the API (rejected — unnecessary bandwidth/complexity); client-supplied storage keys (rejected — cross-tenant risk).

---

## R4. Provider-agnostic structured AI output

**Decision**: Define an `AIClient` `Protocol` with `extract_facts`, `recommend_mapping`, and `explain`. Each provider adapter uses the `openai` SDK pointed at either the OpenAI base URL or the vLLM OpenAI-compatible base URL, and `instructor` to coerce responses into the same pydantic schemas defined in `ai/schemas.py`. Adapters validate the model output before returning; on validation failure they raise, and the orchestrator retries once then fails the run. The analysis code imports only the Protocol and schema types.

**Rationale**: FR-029, FR-030, constitution VI/VIII, tech stack §5. Using the same SDK and the same schemas is what makes provider choice invisible to the analysis logic.

**Alternatives considered**: two different SDKs (rejected — divergent error handling); trusting provider-native JSON mode without schema validation (rejected — fails loud rule); langchain-style wrappers (explicitly out of scope).

---

## R5. Deterministic conflict and duplicate detection

**Decision**: Conflict detection is structural: group candidate facts by `entity_key` + field, and where values differ across source references, emit an item with `has_conflict = true` and `conflict_alternatives = [{value, source_ref}]`. Duplicate detection uses `rapidfuzz` token-set similarity above a configurable threshold as a first pass, tagging likely-duplicate entities for human merge/split; AI is not consulted unless a later requirement demands it. The system never picks a winning value.

**Rationale**: FR-012, FR-013, constitution III/VI.

**Alternatives considered**: AI-based conflict resolution (rejected — violates constitution III); embedding similarity (rejected — vector DB out of scope, unnecessary at this volume).

---

## R6. Insert-only history and the derived accepted dataset

**Decision**: No mutable "current value" column exists. Documents/versions, proposals/items, decisions, validation runs/results, export packages and the audit log are append-only. The accepted dataset is a query returning the latest `Accept`/`Modify` decision per `entity_key`, ordered by round then decision time (`DISTINCT ON (entity_key) ... ORDER BY entity_key, round DESC, decided_at DESC`), indexed on `(project_id, entity_key)`. Locked (accepted/modified) items are carried into later rounds via `carried_from_item_id` and are not sent to the AI again; rejected items are re-included in the next run's input.

**Rationale**: FR-015, FR-016, FR-018, FR-028; constitution VII/V; tech stack §6.

**Alternatives considered**: a materialized snapshot table (rejected — speculative per YAGNI; the derived query is fast at this scale); event sourcing (explicitly out of scope).

---

## R7. `entity_key` stability across rounds

**Decision**: `entity_key` is generated deterministically per entity type in `build_proposal.step` from the entity's natural business identifier (e.g., normalized company code, department code, employee external id), falling back to a deterministic slug of the normalized name when no code exists. The same key is reused across rounds so items can be compared and carried forward. Likely duplicates from R5 are surfaced so humans can merge/split, rather than silently re-keying.

**Rationale**: The PRD risk table flags unstable `entity_key` as the main break of round comparison and locking; FR-015/FR-016 depend on it. Determinism (not AI) keeps it testable.

**Alternatives considered**: random/UUID keys per round (rejected — breaks carry-forward); AI-generated keys (rejected — non-deterministic and untestable).

---

## R8. Validation as plain classes in a registry

**Decision**: Each rule is a class implementing a `ValidationRule` Protocol with `code` and `evaluate(dataset) -> ValidationRuleResult`. A module-level registry lists the five rules: referential integrity, duplicate identifiers, orphaned entities, unresolved conflicts, unacknowledged assumptions. A validation run persists an overall result plus one result row per rule with `failing_records`. Validation runs automatically when the last pending item is resolved and can be re-run manually. A rule raising an exception is treated as `Fail`.

**Rationale**: FR-022, FR-023; constitution V (no rule engine). A registry means adding a rule = one class + one entry.

**Alternatives considered**: JSON-logic/Drools rule engine (rejected — unjustified abstraction for 5 fixed rules).

---

## R9. All-or-nothing Excel export

**Decision**: Generate every artifact into a temporary directory first. Only when all files are produced and validated against the HRMS template headers/column order are they uploaded under `workshop/{tenantId}/{projectId}/exports/v{n}/`, then a single `WorkshopExportPackage` row is inserted with the version number, and the project is transitioned to `Exported` and a `workshop.exported` Kafka event is published. Any failure aborts before upload and creates no package row. Reopening increments the package version on the next export; prior packages are never touched.

**Rationale**: FR-024, FR-025, FR-026; constitution VIII.

**Alternatives considered**: streaming uploads as files are generated (rejected — can leave partial packages); mutating an existing prefix (rejected — violates versioning).

---

## R10. Parsing via one Extractor interface

**Decision**: `ExtractorFactory` selects an extractor by mime type; every extractor returns `ExtractedFact[]` with text plus a `SourceRef` (file, page/sheet, row/cell, optional bbox) and, for OCR, an OCR confidence that acts as a lower bound on item confidence. Tabular reads use `dtype=str` so identifiers like `00123` survive. Raw parsed text is not persisted long-term; it exists only to build source references and feed AI prompts. A parse failure excludes that document from the run and is surfaced, failing the run only if it was the sole document.

**Rationale**: FR-005–FR-008, FR-011; constitution IX; tech stack §4.

**Alternatives considered**: a persisted "parsed document" model (rejected — redundant, YAGNI); per-format branching in the analysis module (rejected — leaks format concerns).

---

## R11. OCR engine choice

**Decision**: Ship behind the `Extractor` interface with Tesseract (`pytesseract`) as the default and PaddleOCR as a selectable implementation. The choice is finalized during a spike on real customer scans; the interface keeps the swap mechanical. OCR confidence flows into item confidence (R10).

**Rationale**: Tech stack §4 and §12 flag OCR accuracy as a real risk requiring a spike; the interface isolates it.

**Alternatives considered**: cloud OCR (possible but adds a data-residency concern for LOCAL_QWEN customers); Docling all-in-one (viable alternative, deferred until the spike).

---

## R12. Schema isolation and migrations in a shared PostgreSQL

**Decision**: All tables live in a dedicated `workshop` schema in the existing PostgreSQL. SQLAlchemy models declare `__table_args__ = {"schema": "workshop"}`; Alembic uses `version_table_schema="workshop"` and schema-qualified operations. The session sets `search_path` to `workshop, public` where joins to platform tables are needed (tenant lookup only). Every query is additionally filtered by `tenant_id`.

**Rationale**: Tech stack §6; keeps the module's data separable without a separate database; tenant isolation.

**Alternatives considered**: a separate database (rejected — backup/migration overhead for no benefit); `public` schema (rejected — clearer ownership with a dedicated schema).

---

## R13. OpenAPI as the frontend contract

**Decision**: FastAPI generates the OpenAPI 3.1 document; it is committed as a snapshot under `contracts/openapi.yaml` and a contract test fails if the generated spec drifts from the snapshot. The React frontend generates its typed client (`openapi-typescript`) from this spec on each build. All request/response bodies are pydantic models with explicit `response_model` and documented error responses.

**Rationale**: Explicit plan requirement; tech stack §8/§12 (prevent API drift).

**Alternatives considered**: hand-written client (rejected — drift); GraphQL (rejected — REST matches the platform and the requirement is a generated REST client).

---

## R14. Outbound events only

**Decision**: Kafka is used solely to publish `workshop.finalized` and `workshop.exported` (payload: project id, tenant id, package version, storage prefix) via `confluent-kafka`. No internal workshop logic consumes Kafka; internal steps are direct service calls or the single Arq queue.

**Rationale**: Plan input and tech stack §6; constitution I/V (no event-sourced internals).

**Alternatives considered**: driving internal flow via events (rejected — event sourcing out of scope).

---

## Summary of resolved unknowns

| Area | Resolution |
|------|------------|
| Auth/authorization | Single `require_project_role` dependency over PyJWT (R1) |
| Async runs | Arq job per run, atomic failure (R2) |
| Uploads/downloads | Pre-signed S3/MinIO URLs (R3) |
| AI abstraction | `AIClient` Protocol + instructor/pydantic, provider-agnostic (R4) |
| Conflict/duplicate | Deterministic structural + rapidfuzz (R5) |
| History/dataset | Insert-only + derived `DISTINCT ON` query (R6) |
| Entity identity | Deterministic `entity_key` (R7) |
| Validation | Plain rule classes + registry (R8) |
| Export | Temp-build, all-or-nothing, versioned (R9) |
| Parsing | One `Extractor` interface, source refs (R10) |
| OCR | Tesseract default, PaddleOCR alternative behind interface (R11) |
| Database | `workshop` schema + Alembic (R12) |
| API contract | Committed OpenAPI snapshot + generated client (R13) |
| Events | Outbound `confluent-kafka` only (R14) |
