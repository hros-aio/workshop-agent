"""Project and membership request/response schemas (mirror contracts/openapi.yaml)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from workshop.common.enums import AIProvider, EntityType, ProjectRole, ProjectStatus
from workshop.common.types import Schema


class ProjectCreate(BaseModel):
    customer_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    scoped_entity_types: list[EntityType] = Field(min_length=1)
    ai_provider: AIProvider
    context_notes: str | None = None

    @field_validator("scoped_entity_types")
    @classmethod
    def _unique(cls, value: list[EntityType]) -> list[EntityType]:
        if len(set(value)) != len(value):
            raise ValueError("scoped_entity_types must be unique")
        return value


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    scoped_entity_types: list[EntityType] | None = Field(default=None, min_length=1)
    ai_provider: AIProvider | None = None
    context_notes: str | None = None


class Project(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    status: ProjectStatus
    ai_provider: AIProvider
    scoped_entity_types: list[EntityType]
    current_round: int
    reopen_count: int
    context_notes: str | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[Project]
    page: int
    page_size: int
    total: int


class TransitionRequest(BaseModel):
    target_status: ProjectStatus
    comment: str | None = None


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=1)


class MemberCreate(BaseModel):
    user_id: uuid.UUID
    role: ProjectRole


class ProjectMember(Schema):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: ProjectRole
    added_by: uuid.UUID
    added_at: datetime


class ProjectOverview(BaseModel):
    project_id: uuid.UUID
    status: ProjectStatus
    current_round: int
    item_counts: dict[str, int]
    validation: dict[str, Any] | None = None
    document_counts: dict[str, int]
    last_export_version: int | None = None


class AuditEvent(Schema):
    id: uuid.UUID
    project_id: uuid.UUID | None = None
    tenant_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    payload: dict[str, Any]
    occurred_at: datetime


class AuditEventPage(BaseModel):
    items: list[AuditEvent]
    page: int
    page_size: int
    total: int
