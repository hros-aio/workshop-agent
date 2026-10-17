"""Integration test: tenant isolation on read endpoints (T113)."""

from __future__ import annotations

import uuid
from typing import Any

from tests.integration.helpers import make_project
from workshop.auth.models import AuthenticatedUser


def test_cross_tenant_read_is_not_found(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID
) -> None:
    session = session_factory()
    project = make_project(session, tenant_id, creator=auth["user"].user_id)
    session.commit()

    other_tenant = uuid.uuid4()
    auth["user"] = AuthenticatedUser(
        user_id=uuid.uuid4(),
        tenant_id=other_tenant,
        global_roles=frozenset({"consultant", "admin"}),
    )

    assert client.get(f"/projects/{project.id}").status_code == 404
    assert client.get(f"/projects/{project.id}/overview").status_code == 404
    assert client.get(f"/projects/{project.id}/documents").status_code == 404
    assert client.get(f"/projects/{project.id}/proposals").status_code == 404
    session.close()
