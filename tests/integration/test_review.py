"""Integration test: decisions are insert-only, locked carry-forward (T077)."""

from __future__ import annotations

import uuid
from typing import Any

from tests.integration.helpers import make_project, seed_proposal_item
from workshop.common.enums import EntityType


def _project(session: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Any:
    project = make_project(session, tenant_id, creator=user_id, scoped=[EntityType.COMPANY])
    session.commit()
    return project


def test_decisions_insert_only_and_comment_enforced(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID
) -> None:
    session = session_factory()
    project = _project(session, tenant_id, auth["user"].user_id)
    item_id = seed_proposal_item(
        session,
        project,
        entity_type=EntityType.COMPANY,
        entity_key="Company:acme",
        value={"name": "Acme", "code": "ACME"},
    )
    session.commit()
    base = f"/projects/{project.id}/proposal-items/{item_id}"

    reject_no_comment = client.post(f"{base}/decisions", json={"action": "Reject"})
    assert reject_no_comment.status_code == 422

    accept = client.post(f"{base}/decisions", json={"action": "Accept"})
    assert accept.status_code == 201, accept.text
    assert accept.json()["action"] == "Accept"

    modify = client.post(
        f"{base}/decisions",
        json={"action": "Modify", "resulting_value": {"name": "Acme Corp"}, "comment": "rename"},
    )
    assert modify.status_code == 201, modify.text

    history = client.get(f"{base}/decisions")
    assert history.status_code == 200
    assert len(history.json()) == 2  # nothing overwritten

    trace = client.get(f"{base}/trace")
    assert trace.status_code == 200
    assert trace.json()["state"] == "Modified"
    session.close()
