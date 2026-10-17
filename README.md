# Workshop Module

AI-assisted HRMS implementation discovery workflow. A single Python/FastAPI
service (API + Arq worker) that turns a customer's raw implementation documents
into a reviewed, validated, versioned HRMS import package.

## Layout

```
src/workshop/
  main.py            FastAPI app factory
  worker.py          Arq worker (processes Analysis Runs)
  settings.py        pydantic-settings configuration
  db.py              SQLAlchemy engine/session; `workshop` schema
  auth/              JWT verification and the single require_project_role dependency
  project/           Project, membership, lifecycle, overview, reopen
  document/          Versioned uploads + S3/MinIO pre-signed URLs
  parsing/           Deterministic extractors (CSV/XLSX/PDF/DOCX/OCR)
  ai/                Provider-agnostic AIClient + OpenAI/LocalQwen adapters
  analysis/          Analysis Run orchestrator and steps
  proposal/          Proposal rounds, derived accepted dataset
  review/            Immutable human decisions
  validation/        Five validation rules + runs
  export/            Template-exact workbooks + reports (all-or-nothing)
  audit/             Append-only business audit trail
  events/            Outbound Kafka producer
migrations/          Alembic migration(s)
specs/001-workshop-discovery/   Feature spec, plan, data model, OpenAPI contract
```

## Requirements

- Python 3.12
- PostgreSQL 15+, Redis 7, an S3-compatible store (MinIO), optionally Kafka
- [`uv`](https://docs.astral.sh/uv/)

## Configuration

Copy `.env.example` to `.env` and adjust. All variables use the `WORKSHOP_`
prefix (see `src/workshop/settings.py`).

Key settings: `WORKSHOP_DATABASE_URL`, `WORKSHOP_REDIS_URL`, `WORKSHOP_S3_*`,
`WORKSHOP_JWT_*`, `WORKSHOP_KAFKA_ENABLED`, `WORKSHOP_OPENAI_API_KEY`,
`WORKSHOP_QWEN_BASE_URL`.

## Install

```bash
uv sync --extra dev
```

## Migrations

```bash
uv run alembic upgrade head
```

## Run

```bash
# API
uv run uvicorn workshop.main:app --reload

# Worker (separate process)
uv run arq workshop.worker.WorkerSettings
```

## OpenAPI

The hand-authored contract lives at
`specs/001-workshop-discovery/contracts/openapi.yaml`. The generated document is
available at `/openapi.json` when the API is running.

## Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Unit tests run anywhere. Integration tests use testcontainers and require Docker
(`pytest -m integration`).
