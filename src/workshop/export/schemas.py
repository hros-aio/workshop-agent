"""Export request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from workshop.common.types import Schema


class ExportFile(Schema):
    name: str
    key: str
    checksum: str


class ExportPackage(Schema):
    id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    storage_prefix: str
    files: list[ExportFile]
    validation_run_id: uuid.UUID
    exported_by: uuid.UUID
    exported_at: datetime


class DownloadUrl(BaseModel):
    url: str
    expires_in: int
