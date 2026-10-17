"""Integration test: overview counts and non-member denial (T102)."""

from __future__ import annotations

import uuid
from typing import Any

from tests.integration.helpers import make_project, seed_accepted_item, seed_proposal_item
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import EntityType


def test_overview_counts(client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID) -> None:
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
        value={"name": "Beta"},
        round_number=2,
        has_conflict=True,
    )
    session.commit()

    response = client.get(f"/projects/{project.id}/overview")
    assert response.status_code == 200, response.text
    counts = response.json()["item_counts"]
    assert counts["accepted"] == 1
    assert counts["pending"] == 1
    assert counts["conflicts"] == 1


def test_overview_non_member_forbidden(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID
) -> None:
    session = session_factory()
    project = make_project(session, tenant_id, creator=uuid.uuid4())
    session.commit()
    auth["user"] = AuthenticatedUser(user_id=uuid.uuid4(), tenant_id=tenant_id, global_roles=frozenset({"consultant"}))
    assert client.get(f"/projects/{project.id}/overview").status_code == 403
    session.close()
