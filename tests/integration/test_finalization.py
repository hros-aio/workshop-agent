"""Integration test: finalization guard (T083)."""

from __future__ import annotations

import uuid
from typing import Any

from tests.integration.helpers import make_project, seed_accepted_item, seed_proposal_item
from workshop.common.enums import EntityType


def test_finalize_blocked_until_resolved_and_passing(
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
    seed_proposal_item(
        session,
        project,
        entity_type=EntityType.COMPANY,
        entity_key="Company:beta",
        value={"name": "Beta", "code": "BETA"},
        round_number=2,
    )
    project.status = "In Review"
    session.commit()
    project_id = str(project.id)

    # A pending item blocks finalization even before validation.
    blocked = client.post(f"/projects/{project_id}/transition", json={"target_status": "Finalized"})
    assert blocked.status_code == 409, blocked.text

    run = client.post(f"/projects/{project_id}/validation-runs")
    assert run.status_code == 201, run.text
    session.close()
