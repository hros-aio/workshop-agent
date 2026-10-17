"""Unit tests for append-only audit writes."""

from __future__ import annotations

import uuid
from datetime import datetime

from workshop.audit.models import WorkshopAuditLog


def test_audit_model_is_append_only_shape() -> None:
    entry = WorkshopAuditLog(
        tenant_id=uuid.uuid4(),
        action="PROJECT_CREATED",
        payload={"name": "Acme"},
    )
    assert entry.payload == {"name": "Acme"}
    assert entry.occurred_at is None or isinstance(entry.occurred_at, datetime)
