"""Integration test: full analysis run with FakeAIClient (T056)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.helpers import add_uploaded_document, csv_bytes, make_project
from workshop.ai.fake import FakeAIClient
from workshop.analysis.jobs import process_analysis_run
from workshop.common.enums import AIProvider, EntityType


@pytest.mark.asyncio
async def test_analysis_run_produces_proposal_and_moves_to_review(
    client: Any, session_factory: Any, auth: dict[str, Any], tenant_id: uuid.UUID, monkeypatch: Any
) -> None:
    session = session_factory()
    project = make_project(
        session,
        tenant_id,
        creator=auth["user"].user_id,
        scoped=[EntityType.COMPANY, EntityType.DEPARTMENT],
        provider=AIProvider.LOCAL_QWEN,
    )
    add_uploaded_document(
        session,
        project,
        uploaded_by=auth["user"].user_id,
        file_name="companies.csv",
        mime_type="text/csv",
        data=csv_bytes([["code", "name"], ["00123", "Acme"], ["00124", "Globex"]]),
    )
    session.commit()
    project_id = str(project.id)

    client.post(f"/projects/{project_id}/transition", json={"target_status": "Collecting Documents"})

    monkeypatch.setattr("workshop.analysis.jobs.for_provider", lambda provider: FakeAIClient())

    triggered = client.post(f"/projects/{project_id}/analysis-runs", json={})
    assert triggered.status_code == 202, triggered.text
    run_id = triggered.json()["id"]

    result = await process_analysis_run({}, run_id)
    assert result == "completed"

    run = client.get(f"/projects/{project_id}/analysis-runs/{run_id}")
    assert run.json()["status"] == "Completed"

    project_response = client.get(f"/projects/{project_id}")
    assert project_response.json()["status"] == "In Review"

    proposals = client.get(f"/projects/{project_id}/proposals")
    assert proposals.status_code == 200, proposals.text
    rounds = proposals.json()
    assert len(rounds) == 1
    assert rounds[0]["round_number"] == 1
    assert rounds[0]["item_counts"]["total"] > 0

    session.close()
