"""Integration test: project create/list/get/update/transition + membership (T033)."""

from __future__ import annotations

import uuid
from typing import Any

from workshop.common.enums import EntityType


def _create_project(client: Any, **overrides: Any) -> dict[str, Any]:
    payload = {
        "name": "Acme Discovery",
        "customer_id": str(uuid.uuid4()),
        "scoped_entity_types": [EntityType.COMPANY.value],
        "ai_provider": "OPENAI",
    }
    payload.update(overrides)
    response = client.post("/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_update_and_transition(client: Any) -> None:
    project = _create_project(client)
    project_id = project["id"]
    assert project["status"] == "Setup"

    updated = client.patch(f"/projects/{project_id}", json={"name": "Renamed"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    listed = client.get("/projects")
    assert listed.status_code == 200
    assert any(p["id"] == project_id for p in listed.json()["items"])

    moved = client.post(f"/projects/{project_id}/transition", json={"target_status": "Collecting Documents"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "Collecting Documents"


def test_disallowed_transition_rejected(client: Any) -> None:
    project = _create_project(client)
    response = client.post(f"/projects/{project['id']}/transition", json={"target_status": "In Review"})
    assert response.status_code == 409


def test_non_member_gets_403(client: Any, auth: dict[str, Any], tenant_id: uuid.UUID) -> None:
    from workshop.auth.models import AuthenticatedUser

    project = _create_project(client)
    auth["user"] = AuthenticatedUser(user_id=uuid.uuid4(), tenant_id=tenant_id, global_roles=frozenset({"consultant"}))
    response = client.get(f"/projects/{project['id']}")
    assert response.status_code == 403
