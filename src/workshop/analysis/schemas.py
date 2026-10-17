"""Analysis Run request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from workshop.common.enums import AIProvider, AnalysisRunStatus
from workshop.common.types import Schema


class AnalysisRunTrigger(BaseModel):
    comment: str | None = None


class AnalysisRun(Schema):
    id: uuid.UUID
    project_id: uuid.UUID
    round_number: int
    status: AnalysisRunStatus
    ai_provider: AIProvider
    document_version_ids: list[uuid.UUID]
    triggered_by: uuid.UUID
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
