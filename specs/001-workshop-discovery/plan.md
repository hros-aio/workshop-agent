# Implementation Plan: Workshop Module — AI-Assisted Discovery Workflow

**Branch**: `001-workshop-discovery` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-workshop-discovery/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Build the Workshop Module as **one Python service** that turns customer implementation documents into a reviewed, validated, versioned HRMS import package. The existing NestJS HRMS server keeps ownership of authentication and tenancy and calls this service directly, forwarding the user's JWT; this service verifies the JWT, checks project membership and role, and does everything else.

The service is stateless HTTP (FastAPI) plus a background worker (Arq/Redis) for long-running Analysis Runs. Deterministic code does parsing, conflict detection, duplicate detection, validation, diffing and Excel generation; AI is used only for reading unstructured documents, proposing mappings/normalization, and writing explanations, strictly behind an `AIClient` Protocol with OpenAI and local Qwen (vLLM, OpenAI-compatible) implementations. History is insert-only; the accepted dataset is a derived query. AI or schema failure fails the whole Analysis Run; no partial proposals and no partial export packages are ever persisted.

The primary deliverable includes a published OpenAPI spec so the React frontend can generate a typed client.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI + uvicorn, pydantic v2, pydantic-settings, SQLAlchemy 2.x, Alembic, Arq (Redis), PyJWT, boto3 (S3/MinIO), confluent-kafka (outbound events only), structlog, pandas + openpyxl (+ xlrd for legacy `.xls`), pdfplumber, python-docx, PaddleOCR or Tesseract (pytesseract), openai SDK + instructor, rapidfuzz, httpx

**Storage**: Existing PostgreSQL — separate `workshop` schema, JSONB for proposal values and source references, insert-only history tables. Existing Redis (Arq queue). Existing S3/MinIO (documents + versioned export packages). Existing Kafka (outbound events only).

**Testing**: pytest + testcontainers (real PostgreSQL/MinIO), fixed sample-document AI regression set run against both providers, ruff (lint/format), mypy (type checking)

**Target Platform**: Linux; one container image, run as API (`uvicorn`) and worker (`arq`) with different commands; Kubernetes

**Project Type**: Single backend web service + background worker

**Performance Goals**: Not a driver. Analysis Runs are asynchronous and may take seconds to minutes. A project is expected to be operated by a small number of users; interactive API responses are expected to feel immediate for the low data volumes involved.

**Constraints**: Correctness over speed (constitution IV); no new services beyond this one; no workflow engine, no event sourcing/CQRS, no vector DB, no agent frameworks; AI provider must not affect analysis behavior; export all-or-nothing; history insert-only; module logic must depend only on the `AIClient` interface.

**Scale/Scope**: A handful of projects per customer per year; hundreds to low thousands of proposal items per project; 6-state lifecycle; ~10 domain modules; ~40 HTTP endpoints.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies |
|---|-----------|------------------------|
| I | AI Proposes, Humans Decide | AI output is persisted only as `ProposalItem`s. Nothing reaches export without an `Accept`/`Modify` `Decision` recording user + timestamp. |
| II | Every Fact Is Traceable | Every item carries `source_refs` (document version + page/sheet + row/cell) or `is_assumption = true`. Export carries the same mapping. |
| III | Conflicts Surfaced, Never Resolved | Conflict detection is structural comparison producing `conflict_alternatives`; the system never selects a winner; validation blocks finalization on unresolved conflicts. |
| IV | Correctness Over Speed | No performance-driven design; async worker used for UX, not throughput. |
| V | YAGNI and Simplicity | One service; enum + guard functions for lifecycle; plain validation-rule classes in a registry; derived accepted dataset query instead of a snapshot table; no speculative features. |
| VI | Deterministic Code Before AI | Parsing, conflict/duplicate detection (rapidfuzz), validation, diffing, export all deterministic; AI limited to extraction, mapping/normalization, explanation. |
| VII | Insert-Only History | Documents/versions, rounds/items, decisions, validation runs, export packages, audit log are append-only; current dataset is derived. |
| VIII | Fail Loudly | Malformed AI output or provider failure → Analysis Run `Failed`, no partial proposal. Export builds in a temp location and uploads only if every file succeeds. |
| IX | Reuse Mature Libraries | Parsing via pandas/openpyxl/pdfplumber/python-docx/PaddleOCR-or-Tesseract; Excel via openpyxl; similarity via rapidfuzz; structured AI output via instructor + pydantic. No custom parsers/OCR/agent framework. |
| Eng | Python 3.12 + type hints + mypy; pydantic at every boundary; provider-agnostic analysis; tests for validation, lifecycle, AI parsing; sample-doc regression; templates matched exactly | All reflected in Technical Context and Project Structure. |
| WF | Traceable to requirements; fake `AIClient`; constitution re-checked in plan | Each module maps to FR groups; `FakeAIClient` is a first-class test fixture. |

**Result**: PASS (no violations, no Complexity Tracking entries required).

## Project Structure

### Documentation (this feature)

```text
specs/001-workshop-discovery/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI 3.1 spec)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
pyproject.toml                     # uv-managed project, ruff + mypy config
alembic.ini
Dockerfile                         # one image; CMD differs for api vs worker
src/workshop/
├── main.py                        # FastAPI app factory, routers, exception handlers
├── worker.py                      # Arq WorkerSettings (analysis_run job)
├── settings.py                    # pydantic-settings (DB, Redis, S3, JWT, Kafka, AI)
├── db.py                          # engine, session factory, workshop schema search_path
├── logging.py                     # structlog configuration
├── auth/
│   ├── jwt.py                     # PyJWT verification (shared key / JWKS)
│   ├── dependencies.py            # current_user, require_project_role() FastAPI dependency
│   └── models.py                  # AuthenticatedUser (id, tenant_id, global roles)
├── common/
│   ├── enums.py                   # ProjectStatus, DocumentStatus, DecisionAction, EntityType, ...
│   ├── errors.py                  # domain exceptions + HTTP mapping
│   └── types.py                   # shared pydantic base models
├── project/
│   ├── router.py
│   ├── service.py
│   ├── models.py                  # WorkshopProject, WorkshopProjectMember
│   ├── schemas.py                 # request/response pydantic models
│   └── lifecycle.py               # ALLOWED_TRANSITIONS + assert_transition + guards
├── document/
│   ├── router.py
│   ├── service.py
│   ├── models.py                  # WorkshopDocument, WorkshopDocumentVersion
│   ├── schemas.py
│   └── storage.py                 # S3 presigned PUT/GET adapter
├── parsing/
│   ├── service.py                 # ExtractorFactory + parse pipeline
│   ├── models.py                  # ExtractedFact, SourceRef
│   └── extractors/
│       ├── base.py                # Extractor Protocol
│       ├── pdf_extractor.py
│       ├── docx_extractor.py
│       ├── tabular_extractor.py   # CSV/XLSX via pandas+openpyxl (dtype=str)
│       └── image_ocr_extractor.py # PaddleOCR / Tesseract
├── ai/
│   ├── client.py                  # AIClient Protocol + request/response models
│   ├── factory.py                 # resolve AIClient per project.ai_provider
│   ├── schemas.py                 # pydantic structured-output schemas (validated per call)
│   ├── prompts.py                 # plain template functions
│   ├── fake.py                    # FakeAIClient for tests/full-flow without a model
│   └── providers/
│       ├── openai_client.py
│       └── local_qwen_client.py
├── analysis/
│   ├── router.py                  # trigger + status endpoints
│   ├── service.py                 # orchestrator ("Workshop Agent"), provider-agnostic
│   ├── models.py                  # WorkshopAnalysisRun
│   ├── jobs.py                    # Arq task: process_analysis_run
│   └── steps/
│       ├── extract_facts.py
│       ├── detect_conflicts.py    # structural
│       ├── detect_duplicates.py   # rapidfuzz
│       ├── recommend_mapping.py
│       └── build_proposal.py      # entity_key + carry-forward/locking
├── proposal/
│   ├── router.py
│   ├── service.py                 # current-accepted-dataset derived query, round compare
│   ├── models.py                  # WorkshopProposal, WorkshopProposalItem
│   └── schemas.py
├── review/
│   ├── router.py
│   ├── service.py
│   └── models.py                  # WorkshopDecision (insert-only)
├── validation/
│   ├── router.py
│   ├── service.py
│   ├── models.py                  # WorkshopValidationRun, WorkshopValidationResult
│   ├── registry.py
│   ├── rules.py                   # one class per rule (5 rules)
│   └── base.py                    # ValidationRule Protocol
├── export/
│   ├── router.py
│   ├── service.py                 # temp build → upload all-or-nothing → package row
│   ├── templates/                 # HRMS standard import template headers
│   ├── models.py                  # WorkshopExportPackage
│   └── generators/
│       ├── excel_package.py
│       ├── difference_report.py
│       ├── validation_report.py
│       └── decision_log.py
├── audit/
│   ├── service.py
│   └── models.py                  # WorkshopAuditLog (append-only)
└── events/
    └── producer.py                # confluent-kafka outbound (workshop.exported, workshop.finalized)

migrations/                        # Alembic, version_table_schema=workshop, schema-qualified
tests/
├── contract/                      # OpenAPI snapshot + client-generation smoke test
├── integration/                   # testcontainers: Postgres + MinIO; Arq job runs e2e
└── unit/                          # lifecycle guards, validation rules, AI-schema parsing, parsers
tests/fixtures/sample_documents/   # AI regression set (fixed documents + expected extractions)
```

**Structure Decision**: Single-project layout under `src/workshop/` with one package folder per domain module named in the plan input (project, document, parsing, ai, analysis, proposal, review, validation, export, audit), plus small cross-cutting packages (`auth`, `common`, `events`). Each module owns its router, service, models and schemas so it is independently testable and has one reason to change. The service is one deployable image; `main.py` runs the API and `worker.py` runs the Arq worker.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. No entries.
