"""Integration test: provider-independent proposal structure (T109)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.helpers import add_uploaded_document, csv_bytes, make_project
from workshop.ai.fake import FakeAIClient
from workshop.analysis.models import WorkshopAnalysisRun
from workshop.analysis.service import run_analysis
from workshop.common.enums import AIProvider, EntityType


@pytest.mark.parametrize("provider", [AIProvider.OPENAI, AIProvider.LOCAL_QWEN])
def test_proposal_structure_is_provider_independent(
    provider: AIProvider,
    session_factory: Any,
    auth: dict[str, Any],
    tenant_id: uuid.UUID,
) -> None:
    session = session_factory()
    project = make_project(session, tenant_id, creator=auth["user"].user_id, provider=provider)
    version = add_uploaded_document(
        session,
        project,
        uploaded_by=auth["user"].user_id,
        file_name="companies.csv",
        mime_type="text/csv",
        data=csv_bytes([["code", "name"], ["00123", "Acme"]]),
    )
    run = WorkshopAnalysisRun(
        project_id=project.id,
        round_number=1,
        status="Running",
        ai_provider=provider.value,
        document_version_ids=[version.id],
        triggered_by=auth["user"].user_id,
    )
    session.add(run)
    session.flush()

    proposal = run_analysis(session, project=project, run=run, ai=FakeAIClient())
    session.commit()

    assert proposal.round_number == 1
    assert all(item.entity_type == EntityType.COMPANY.value for item in proposal.items)
    assert all(item.source_refs for item in proposal.items)
    session.close()
