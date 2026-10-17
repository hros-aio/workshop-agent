"""Append-only business audit trail: writer and reader."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workshop.audit.models import WorkshopAuditLog
from workshop.common.enums import AuditAction


def record(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action: AuditAction,
    project_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> WorkshopAuditLog:
    entry = WorkshopAuditLog(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor_id,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    session.add(entry)
    session.flush()
    return entry


def list_events(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    action: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[WorkshopAuditLog], int]:
    conditions = [
        WorkshopAuditLog.tenant_id == tenant_id,
        WorkshopAuditLog.project_id == project_id,
    ]
    if action:
        conditions.append(WorkshopAuditLog.action == action)
    if from_time:
        conditions.append(WorkshopAuditLog.occurred_at >= from_time)
    if to_time:
        conditions.append(WorkshopAuditLog.occurred_at <= to_time)

    total = session.scalar(select(func.count()).select_from(WorkshopAuditLog).where(*conditions)) or 0
    rows = (
        session.execute(
            select(WorkshopAuditLog)
            .where(*conditions)
            .order_by(WorkshopAuditLog.occurred_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total
