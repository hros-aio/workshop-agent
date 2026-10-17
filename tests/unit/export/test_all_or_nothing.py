"""Unit tests: export is all-or-nothing (T090)."""

from __future__ import annotations

import uuid

import pytest

from workshop.common.enums import EntityType, ProjectStatus, ValidationOutcome
from workshop.export import service as export_service
from workshop.export import templates
from workshop.export.models import WorkshopExportPackage


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def scalar(self, _stmt: object) -> int:
        return 0


class _User:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()


class _Project:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.status = ProjectStatus.FINALIZED.value
        self.scoped_entity_types = [EntityType.COMPANY.value]


class _Run:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.overall_result = ValidationOutcome.PASS.value
        self.round_number = 1


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export_service.validation_service, "latest_validation_run", lambda *a, **k: _Run())
    monkeypatch.setattr(export_service.validation_service, "results_for_run", lambda *a, **k: [])
    monkeypatch.setattr(export_service.proposal_service, "accepted_dataset", lambda *a, **k: [])
    monkeypatch.setattr(export_service, "_decision_log_rows", lambda *a, **k: [])


def test_success_creates_package_with_complete_file_list(patched: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export_service.storage, "upload_bytes", lambda *a, **k: None)
    session = _Session()
    package = export_service.create_export(session, _User(), _Project())
    names = {entry["name"] for entry in package.files}
    assert names == set(templates.file_names_for([EntityType.COMPANY.value])) | {
        templates.DIFFERENCE_REPORT_FILE,
        templates.VALIDATION_REPORT_FILE,
        templates.DECISION_LOG_FILE,
    }
    assert any(isinstance(obj, WorkshopExportPackage) for obj in session.added)


def test_failure_on_upload_creates_no_package_row(patched: None, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _flaky(key: str, data: bytes, *, content_type: str) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("storage down")

    monkeypatch.setattr(export_service.storage, "upload_bytes", _flaky)
    monkeypatch.setattr(export_service.storage, "delete_object", lambda *a, **k: None)
    session = _Session()
    with pytest.raises(RuntimeError):
        export_service.create_export(session, _User(), _Project())
    assert not any(isinstance(obj, WorkshopExportPackage) for obj in session.added)
