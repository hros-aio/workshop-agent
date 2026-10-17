"""Validation request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from workshop.common.enums import ValidationOutcome
from workshop.common.types import Schema


class ValidationRuleResultOut(Schema):
    rule_code: str
    result: ValidationOutcome
    failing_records: list[dict[str, Any]] | None = None


class ValidationRun(Schema):
    id: uuid.UUID
    project_id: uuid.UUID
    round_number: int
    triggered_by: uuid.UUID
    triggered_at: datetime
    overall_result: ValidationOutcome
    results: list[ValidationRuleResultOut] = []


class FinalizeRequest(BaseModel):
    comment: str | None = None
