"""Shared pytest fixtures.

Integration tests rely on testcontainers (PostgreSQL + MinIO). Unit tests do not
need Docker and run everywhere. The integration fixtures are resolved lazily so
that unit test collection never starts a container.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("WORKSHOP_JWT_SECRET", "test-secret")
os.environ.setdefault("WORKSHOP_KAFKA_ENABLED", "false")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
