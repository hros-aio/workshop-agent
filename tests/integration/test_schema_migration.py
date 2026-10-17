"""Integration test: the workshop schema and tables exist after migration (T031)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def test_workshop_schema_present(session_factory: Any) -> None:
    session = session_factory()
    try:
        rows = session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'workshop'")
        ).all()
    finally:
        session.close()
    tables = {row[0] for row in rows}
    assert "workshop_project" in tables
    assert "workshop_document_version" in tables
    assert "workshop_analysis_run" in tables
    assert "workshop_proposal_item" in tables
    assert "workshop_decision" in tables
    assert "workshop_validation_run" in tables
    assert "workshop_export_package" in tables
    assert "workshop_audit_log" in tables
