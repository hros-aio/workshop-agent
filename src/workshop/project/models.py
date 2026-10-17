"""Project aggregate and project-scoped membership."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workshop.common.enums import AIProvider, ProjectStatus
from workshop.db import Base


class WorkshopProject(Base):
    __tablename__ = "workshop_project"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=ProjectStatus.SETUP.value)
    ai_provider: Mapped[str] = mapped_column(String(20), nullable=False, default=AIProvider.OPENAI.value)
    scoped_entity_types: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list[WorkshopProjectMember]] = relationship(back_populates="project", cascade="all, delete-orphan")


class WorkshopProjectMember(Base):
    __tablename__ = "workshop_project_member"
    __table_args__ = (UniqueConstraint("project_id", "user_id", "role", name="uq_member_project_user_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshop_project.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    project: Mapped[WorkshopProject] = relationship(back_populates="members")
