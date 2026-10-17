"""Integration test: AI failure / invalid output fails the run atomically (T057)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select

from tests.integration.helpers import add_uploaded_document, csv_bytes, make_project
from workshop.ai.fake import FakeAIClient
from workshop.analysis.jobs import process_analysis_run
from workshop.common.enums import AIProvider, EntityType
from workshop.proposal.models import WorkshopProposal


@pytest.mark.parametrize("mode", ["fail", "invalid"])
@pytest.mark.asyncio
async def test_failed_run_persists_no_proposal(
    mode: str,
    client: Any,
    session_factory: Any,
    auth: dict[str, Any],
    tenant_id: uuid.UUID,
    monkeypatch: Any,
) -> None:
    session = session_factory()
    project = make_project(
        session,
        tenant_id,
        creator=auth["user"].user_id,
        scoped=[EntityType.COMPANY],
        provider=AIProvider.LOCAL_QWEN,
    )
    add_uploaded_document(
        session,
        project,
        uploaded_by=auth["user"].user_id,
        file_name="companies.csv",
        mime_type="text/csv",
        data=csv_bytes([["code", "name"], ["00123", "Acme"]]),
    )
    session.commit()
    project_id = str(project.id)
    client.post(f"/projects/{project_id}/transition", json={"target_status": "Collecting Documents"})

    fake = FakeAIClient(fail=mode == "fail", invalid=mode == "invalid")
    monkeypatch.setattr("workshop.analysis.jobs.for_provider", lambda provider: fake)

    triggered = client.post(f"/projects/{project_id}/analysis-runs", json={})
    run_id = triggered.json()["id"]

    result = await process_analysis_run({}, run_id)
    assert result == "failed"

    run = client.get(f"/projects/{project_id}/analysis-runs/{run_id}")
    body = run.json()
    assert body["status"] == "Failed"
    assert body["error_message"]

    # No proposal or items persisted; the project stays In Analysis.
    count = session.scalar(
        select(func.count()).select_from(WorkshopProposal).where(WorkshopProposal.project_id == project.id)
    )
    assert count == 0
    assert client.get(f"/projects/{project_id}").json()["status"] == "In Analysis"
    session.close()
