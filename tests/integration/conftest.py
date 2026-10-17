"""Integration fixtures: real PostgreSQL + MinIO via testcontainers.

Tests are skipped automatically when Docker is not available so the default
`pytest` run stays green on machines without Docker.
"""

from __future__ import annotations

import contextlib
import shutil
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.fixture(scope="session", autouse=True)
def _require_docker() -> Iterator[None]:
    if not _docker_available():
        pytest.skip("Docker is not available")
    yield


@pytest.fixture(scope="session")
def postgres_url(_require_docker: None) -> Iterator[str]:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as container:
        url = container.get_connection_url().replace("postgresql+psycopg2", "postgresql+psycopg")
        yield url


@pytest.fixture(scope="session")
def storage(_require_docker: None) -> Iterator[Any]:
    from testcontainers.minio import MinioContainer

    with MinioContainer() as container:
        yield container


@pytest.fixture(scope="session")
def app_env(postgres_url: str, storage: Any) -> Iterator[None]:
    import os

    settings = storage.get_container_host_ip()
    port = storage.get_exposed_port(9000)
    os.environ["WORKSHOP_DATABASE_URL"] = postgres_url
    os.environ["WORKSHOP_S3_ENDPOINT_URL"] = f"http://{settings}:{port}"
    os.environ["WORKSHOP_S3_ACCESS_KEY_ID"] = storage.access_key
    os.environ["WORKSHOP_S3_SECRET_ACCESS_KEY"] = storage.secret_key
    os.environ["WORKSHOP_S3_BUCKET"] = "workshop"
    os.environ["WORKSHOP_S3_FORCE_PATH_STYLE"] = "true"
    os.environ["WORKSHOP_KAFKA_ENABLED"] = "false"

    from workshop import db as db_module
    from workshop.settings import get_settings

    get_settings.cache_clear()
    db_module._engine = None
    db_module._session_factory = None

    import boto3
    from botocore.client import Config

    client = boto3.client(
        "s3",
        endpoint_url=f"http://{settings}:{port}",
        aws_access_key_id=storage.access_key,
        aws_secret_access_key=storage.secret_key,
        config=Config(s3={"addressing_style": "path"}),
    )
    with contextlib.suppress(Exception):
        client.create_bucket(Bucket="workshop")

    db_module.create_all_for_tests()
    yield


@pytest.fixture
def session_factory(app_env: None) -> Any:
    from workshop.db import get_session_factory

    return get_session_factory()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def auth(tenant_id: uuid.UUID) -> dict[str, Any]:
    from workshop.auth.models import AuthenticatedUser

    return {
        "user": AuthenticatedUser(user_id=uuid.uuid4(), tenant_id=tenant_id, global_roles=frozenset({"consultant"}))
    }


@pytest.fixture
def client(app_env: None, auth: dict[str, Any]) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from workshop.auth.dependencies import get_current_user, get_db
    from workshop.db import get_session_factory
    from workshop.main import app

    def _current_user() -> Any:
        return auth["user"]

    def _db() -> Iterator[Any]:
        session = get_session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_db] = _db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
