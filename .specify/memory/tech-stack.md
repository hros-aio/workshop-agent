# Tech Stack: Workshop Module

**Status**: Draft v1.0
**Scope**: Technology choices for the Workshop Module, based on the Workshop Module PRD
**Guiding rules**: YAGNI, simplicity, correctness over speed, reuse mature open-source libraries

---

## 1. Summary of the Decision

The Workshop Module backend is a **single Python service (FastAPI)**. The existing NestJS HRMS server does **not** contain workshop code. It handles authentication and tenancy only, and calls the Python Workshop API directly.

Reasons for choosing Python:
- Best ecosystem for document parsing (PDF, Word, Excel), OCR, and AI integration.
- One language for all workshop logic: no duplicated schemas between languages, no Node parsing libraries.
- The module runs only a few times a year, so a separate service adds little operational cost.

---

## 2. High-Level Shape

```
React (TanStack)
      │
      ▼
Existing NestJS HRMS server  (auth + tenancy only)
      │  REST call, forwards the user's JWT
      ▼
Python Workshop API (FastAPI)
  projects · documents · parsing · AI · proposals
  review · validation · export · audit
      │
      ├──▶ PostgreSQL        (workshop schema, insert-only history)
      ├──▶ Redis             (job queue for Analysis Runs)
      ├──▶ S3 / MinIO        (source documents + export packages)
      ├──▶ Kafka             (outbound events only, e.g. workshop.exported)
      └──▶ AIClient ──▶ OpenAI  or  self-hosted Qwen3.5-27B (vLLM)
```

---

## 3. Backend (Python Workshop Service)

| Concern | Choice | Notes |
|---|---|---|
| Runtime | **Python 3.12** | |
| Packaging | **uv** | Fast, reproducible installs |
| Web framework | **FastAPI + uvicorn** | Auto-generated OpenAPI spec for frontend and NestJS teams |
| Validation / schemas | **pydantic v2** | API models and validation of every AI response |
| ORM | **SQLAlchemy 2.x** | |
| Migrations | **Alembic** | |
| Background jobs | **Arq** (or RQ) on Redis | Long-running Analysis Runs stay off the HTTP request |
| Auth | **PyJWT** | Verifies the platform's existing JWT; no new auth system |
| Permissions | One FastAPI dependency | Project-membership check plus platform roles |
| Object storage client | **boto3** | Works with both S3 and MinIO |
| Kafka client | **confluent-kafka** | Outbound events only |
| Logging | **structlog** | Operational logs; business audit lives in `workshop_audit_log` |
| Config / secrets | **pydantic-settings** + Kubernetes Secrets | |

---

## 4. Document Parsing (Deterministic, No AI)

| Format | Library | Notes |
|---|---|---|
| CSV / Excel (read) | **pandas + openpyxl** | Use `dtype=str` so codes like `00123` are not corrupted; add `xlrd` for old `.xls` |
| PDF | **pdfplumber** (or **PyMuPDF**) | pdfplumber gives page and position for source references |
| Word (.docx) | **python-docx** | Paragraphs and tables |
| Scanned images / PDFs | **PaddleOCR** or **Tesseract (pytesseract)** | Test on real customer scans before committing |
| All-in-one alternative | **Docling** | One library for PDF, DOCX and scans with OCR |

All extractors produce one common `ExtractedFact` model (text, file, page or sheet, row or cell) so every proposal value can be traced to its source.

---

## 5. AI Layer

| Concern | Choice | Notes |
|---|---|---|
| SDK | **openai** (Python) | Same SDK for both providers; Qwen via vLLM's OpenAI-compatible endpoint with a different `base_url` |
| Structured output | **pydantic + instructor** | Every AI response is validated against a schema; invalid output fails the run and never becomes a proposal item |
| Abstraction | Python `Protocol` named `AIClient` | Implementations: `OpenAIClient`, `LocalQwenClient` |
| Provider selection | Per project (`ai_provider` = `OPENAI` or `LOCAL_QWEN`) | Workshop logic never knows which model is used |
| Local model serving | **vLLM** on a GPU node pool | Use guided / structured JSON decoding for Qwen |
| Duplicate detection | **rapidfuzz** | Deterministic first pass before involving AI |
| Prompts | Plain template functions in source control | No prompt-management framework |

Rule: deterministic code handles conflicts, duplicates, validation and diffing. AI is used only for reading unstructured content, proposing mappings and normalization, and writing plain-language explanations.

---

## 6. Data and Infrastructure

| Concern | Choice | Notes |
|---|---|---|
| Database | **PostgreSQL** (existing) | Separate `workshop` schema; JSONB for proposal values and source references; insert-only history tables |
| Queue / cache | **Redis** (existing) | Backs Arq |
| Object storage | **S3 / MinIO** (existing) | Documents and exports under versioned key prefixes; pre-signed URLs for upload and download |
| Events | **Kafka** (existing) | Outbound domain events only; not used to drive internal workshop logic |
| Orchestration | **Kubernetes** (existing) | |
| Container | One Python image | Run as API (`uvicorn`) and worker (`arq`) with different commands |

---

## 7. Excel Export

| Concern | Choice | Notes |
|---|---|---|
| Generate import package | **openpyxl** (or **XlsxWriter**) | Output must match the HRMS standard import templates exactly |
| Reports | openpyxl | Difference Report, Validation Report, Decision Log |

Export is all-or-nothing: generate everything in a temporary location, upload only if every file succeeds, so no partial package is ever stored.

---

## 8. Frontend

| Concern | Choice |
|---|---|
| Framework | **React** (existing) |
| Server state | **TanStack Query** |
| Tables (proposal items, documents, decisions) | **TanStack Table** |
| Routing | **TanStack Router** (or existing router) |
| Forms (review / modify) | **TanStack Form** + **zod** |
| API client | Generated from FastAPI's OpenAPI spec (e.g. **openapi-typescript**) |
| Source document viewer | **react-pdf** for PDFs; simple table view for Excel sources |
| Round comparison | Plain side-by-side table |

---

## 9. Testing and Quality

| Concern | Choice |
|---|---|
| Unit and integration tests | **pytest** |
| Database tests | **testcontainers** (real PostgreSQL) |
| AI regression tests | Fixed set of sample documents with expected extractions, run against both providers |
| Lint / format | **ruff** |
| Type checking | **mypy** |

The sample-document regression set is the most valuable test asset in this module.

---

## 10. Integration with the Existing NestJS HRMS Server

- NestJS stays responsible for **authentication, tenancy and users** only.
- The frontend calls the Python Workshop API either through a thin NestJS proxy route or through ingress routing of `/workshop-api/*` directly to the Python service.
- The user's JWT is forwarded; Python verifies it using the shared signing key or JWKS endpoint.
- Tenant ID and roles come from JWT claims.
- The Python service never writes to production HRMS data. Its only output is the exported Implementation Package, consumed by the existing, separate import process.

---

## 11. Deliberately Not Used

| Not used | Reason |
|---|---|
| LangChain, LlamaIndex | A prompt, a pydantic schema and a validated response are enough |
| LangGraph, CrewAI, AutoGen | Single orchestrated flow, not an agent system |
| Vector database / embeddings | No requirement for semantic search over a corpus |
| Temporal / workflow engines | Six fixed statuses, implemented as an enum with guard functions |
| Event sourcing / CQRS | Insert-only tables plus an audit log meet the auditability need |
| Elasticsearch | Data volumes are tiny |
| Additional microservices | One Python service is the only new deployable |

---

## 12. Trade-offs and Risks

| Item | Impact | Mitigation |
|---|---|---|
| First module outside the NestJS codebase | Team must own a Python service | Keep the service small; one image, one repo |
| JWT trust between NestJS and Python | Auth coupling | Shared JWKS or signing key; tenant and roles in claims |
| No shared types with frontend | Possible API drift | Generate the TypeScript client from OpenAPI on every build |
| OCR accuracy on poor scans | Low-quality extraction | Spike on real customer scans; swap engine behind one interface |
| Qwen structured-output reliability | More failed runs | vLLM guided decoding, small per-entity prompts, pydantic validation plus one retry |
| GPU infrastructure for local Qwen | Extra deployment | Optional; only needed for projects using `LOCAL_QWEN` |

---

## 13. Final Stack at a Glance

- **Backend**: Python 3.12, FastAPI, pydantic, SQLAlchemy, Alembic, Arq
- **Parsing**: pandas, openpyxl, pdfplumber, python-docx, PaddleOCR or Tesseract (or Docling)
- **AI**: openai SDK, instructor, vLLM (Qwen3.5-27B), rapidfuzz
- **Data**: PostgreSQL, Redis, S3 / MinIO, Kafka
- **Frontend**: React, TanStack (Query, Table, Router, Form), react-pdf
- **Quality**: pytest, testcontainers, ruff, mypy
- **Deploy**: Kubernetes (one new Python Deployment, plus optional vLLM GPU Deployment)