"""Integration test: provenance of an exported value (T099)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from tests.integration.helpers import make_project, seed_proposal_item
from workshop.common.enums import EntityType


def test_trace_returns_source_refs_and_decision(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID
) -> None:
    session: Session = session_factory()
    project = make_project(session, tenant_id, creator=auth["user"].user_id)
    item_id = seed_proposal_item(
        session,
        project,
        entity_type=EntityType.COMPANY,
        entity_key="Company:acme",
        value={"name": "Acme"},
    )
    # Attach a source reference to the item.
    from workshop.proposal.models import WorkshopProposalItem

    item = session.get(WorkshopProposalItem, item_id)
    assert item is not None
    item.source_refs = [
        {
            "file_name": "companies.csv",
            "document_version_id": None,
            "page": None,
            "sheet": "Sheet1",
            "row": 2,
            "cell": "B2",
        }
    ]
    session.commit()

    base = f"/projects/{project.id}/proposal-items/{item_id}"
    accepted = client.post(f"{base}/decisions", json={"action": "Accept"})
    assert accepted.status_code == 201

    trace = client.get(f"{base}/trace")
    assert trace.status_code == 200, trace.text
    body = trace.json()
    assert body["source_refs"][0]["file_name"] == "companies.csv"
    assert body["latest_decision"]["action"] == "Accept"
    assert body["latest_decision"]["decided_by"]
    assert body["is_assumption"] is False
    session.close()
