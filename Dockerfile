FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

# Default command runs the API. Override with the worker command in the
# worker deployment: `arq workshop.worker.WorkerSettings`.
EXPOSE 8000
CMD ["uvicorn", "workshop.main:app", "--host", "0.0.0.0", "--port", "8000"]
