"""Review request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from workshop.common.enums import DecisionAction
from workshop.common.types import Schema


class DecisionCreate(BaseModel):
    action: DecisionAction
    resulting_value: dict[str, Any] | None = None
    comment: str | None = None


class Decision(Schema):
    id: uuid.UUID
    proposal_item_id: uuid.UUID
    action: DecisionAction
    resulting_value: dict[str, Any]
    comment: str | None = None
    decided_by: uuid.UUID
    decided_at: datetime
    reopened: bool
