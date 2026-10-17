"""Validation runs and per-rule results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workshop.db import Base


class WorkshopValidationRun(Base):
    __tablename__ = "workshop_validation_run"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_project.id"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    overall_result: Mapped[str] = mapped_column(String(10), nullable=False)

    results: Mapped[list[WorkshopValidationResult]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan"
    )


class WorkshopValidationResult(Base):
    __tablename__ = "workshop_validation_result"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    validation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_validation_run.id"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    failing_records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    validation_run: Mapped[WorkshopValidationRun] = relationship(back_populates="results")
