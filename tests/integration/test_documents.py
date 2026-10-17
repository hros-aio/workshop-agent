"""Integration test: document version/supersede + download URL (T045)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from workshop.common.enums import EntityType
from workshop.document import storage


def _project(client: Any) -> str:
    response = client.post(
        "/projects",
        json={
            "name": "Docs",
            "customer_id": str(uuid.uuid4()),
            "scoped_entity_types": [EntityType.COMPANY.value],
            "ai_provider": "OPENAI",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_complete_replace_and_download(client: Any) -> None:
    project_id = _project(client)

    created = client.post(
        f"/projects/{project_id}/documents",
        json={
            "document_type": "intake",
            "file_name": "companies.csv",
            "mime_type": "text/csv",
            "size_bytes": 10,
        },
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    document_id = ticket["document_id"]
    version_id = ticket["version_id"]

    payload = b"code,name\n00123,Acme\n"
    storage.upload_bytes(ticket["storage_key"], payload, content_type="text/csv")
    checksum = hashlib.sha256(payload).hexdigest()

    completed = client.post(
        f"/projects/{project_id}/documents/{document_id}/versions/{version_id}/complete",
        json={"checksum_sha256": checksum},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["upload_status"] == "Uploaded"

    # Replace with a second version; the first is superseded, never deleted.
    newer = client.post(
        f"/projects/{project_id}/documents/{document_id}/versions",
        json={
            "file_name": "companies_v2.csv",
            "mime_type": "text/csv",
            "size_bytes": 12,
        },
    )
    assert newer.status_code == 201, newer.text
    v2 = newer.json()
    storage.upload_bytes(v2["storage_key"], b"code,name\n00124,Beta\n", content_type="text/csv")
    client.post(
        f"/projects/{project_id}/documents/{document_id}/versions/{v2['version_id']}/complete",
        json={"checksum_sha256": "abc"},
    )

    detail = client.get(f"/projects/{project_id}/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    versions = detail.json()["versions"]
    assert len(versions) == 2
    assert versions[0]["superseded_at"] is not None

    url = client.get(f"/projects/{project_id}/documents/{document_id}/versions/{version_id}/download-url")
    assert url.status_code == 200
    assert "url" in url.json()
