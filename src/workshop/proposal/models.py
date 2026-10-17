"""Immutable proposal rounds and their items."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workshop.db import Base


class WorkshopProposal(Base):
    __tablename__ = "workshop_proposal"
    __table_args__ = (UniqueConstraint("project_id", "round_number", name="uq_proposal_project_round"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_project.id"), nullable=False, index=True
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_analysis_run.id"), nullable=False, unique=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    items: Mapped[list[WorkshopProposalItem]] = relationship(back_populates="proposal")


class WorkshopProposalItem(Base):
    __tablename__ = "workshop_proposal_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_proposal.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    proposed_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    is_assumption: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflict_alternatives: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    likely_duplicate_of: Mapped[str | None] = mapped_column(String(300), nullable=True)
    carried_from_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_proposal_item.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    proposal: Mapped[WorkshopProposal] = relationship(back_populates="items")
