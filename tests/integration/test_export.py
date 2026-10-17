"""Integration test: export package contents, template match, download (T091)."""

from __future__ import annotations

import uuid
from typing import Any

from tests.integration.helpers import make_project, seed_accepted_item
from workshop.common.enums import EntityType
from workshop.export import templates


def _finalized_project(client: Any, session: Any, auth: dict[str, Any], tenant_id: uuid.UUID) -> str:
    project = make_project(session, tenant_id, creator=auth["user"].user_id, scoped=[EntityType.COMPANY])
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

    validation = client.post(f"/projects/{project_id}/validation-runs")
    assert validation.status_code == 201, validation.text
    assert validation.json()["overall_result"] == "Pass"

    finalized = client.post(f"/projects/{project_id}/transition", json={"target_status": "Finalized"})
    assert finalized.status_code == 200, finalized.text
    return project_id


def test_export_contains_expected_artifacts(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID
) -> None:
    session = session_factory()
    project_id = _finalized_project(client, session, auth, tenant_id)

    created = client.post(f"/projects/{project_id}/exports")
    assert created.status_code == 201, created.text
    package = created.json()
    names = {f["name"] for f in package["files"]}
    assert names == set(templates.file_names_for([EntityType.COMPANY.value])) | {
        templates.DIFFERENCE_REPORT_FILE,
        templates.VALIDATION_REPORT_FILE,
        templates.DECISION_LOG_FILE,
    }
    assert package["version_number"] == 1

    listed = client.get(f"/projects/{project_id}/exports")
    assert len(listed.json()) == 1

    url = client.get(f"/projects/{project_id}/exports/1/files/{templates.DIFFERENCE_REPORT_FILE}/download-url")
    assert url.status_code == 200
    assert "url" in url.json()

    assert client.get(f"/projects/{project_id}").json()["status"] == "Exported"
    session.close()
