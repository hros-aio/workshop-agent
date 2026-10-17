"""Integration test: reopen -> re-export creates a new version, prior intact (T106)."""

from __future__ import annotations

import uuid
from typing import Any

from tests.integration.helpers import make_project, seed_accepted_item
from workshop.common.enums import EntityType


def test_reopen_then_reexport_versions_packages(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID
) -> None:
    session = session_factory()
    project = make_project(session, tenant_id, creator=auth["user"].user_id)
    seed_accepted_item(
        session,
        project,
        entity_type=EntityType.COMPANY,
        entity_key="Company:acme",
        value={"name": "Acme", "code": "ACME"},
    )
    project.status = "In Review"
    session.commit()
    project_id = str(project.id)

    client.post(f"/projects/{project_id}/validation-runs")
    client.post(f"/projects/{project_id}/transition", json={"target_status": "Finalized"})
    first = client.post(f"/projects/{project_id}/exports")
    assert first.status_code == 201, first.text
    assert first.json()["version_number"] == 1

    reopened = client.post(f"/projects/{project_id}/reopen", json={"reason": "scope changed"})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "In Review"
    assert reopened.json()["reopen_count"] == 1

    client.post(f"/projects/{project_id}/validation-runs")
    client.post(f"/projects/{project_id}/transition", json={"target_status": "Finalized"})
    second = client.post(f"/projects/{project_id}/exports")
    assert second.status_code == 201, second.text
    assert second.json()["version_number"] == 2

    packages = client.get(f"/projects/{project_id}/exports").json()
    assert [p["version_number"] for p in packages] == [2, 1]
    session.close()
