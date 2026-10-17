"""Document request/response schemas (mirror contracts/openapi.yaml)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from workshop.common.enums import DocumentStatus
from workshop.common.types import Schema


class DocumentCreate(BaseModel):
    document_type: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    mime_type: str
    size_bytes: int = Field(ge=1)
    notes: str | None = None


class DocumentVersionCreate(BaseModel):
    file_name: str = Field(min_length=1)
    mime_type: str
    size_bytes: int = Field(ge=1)
    notes: str | None = None


class DocumentVersionComplete(BaseModel):
    checksum_sha256: str = Field(min_length=1)


class DocumentUploadTicket(BaseModel):
    document_id: uuid.UUID
    version_id: uuid.UUID
    upload_url: str
    storage_key: str
    expires_at: datetime


class DocumentVersion(Schema):
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    file_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    upload_status: str
    uploaded_by: uuid.UUID
    uploaded_at: datetime | None = None
    superseded_at: datetime | None = None


class Document(Schema):
    id: uuid.UUID
    project_id: uuid.UUID
    document_type: str
    status: DocumentStatus
    current_version_id: uuid.UUID | None = None
    notes: str | None = None
    created_by: uuid.UUID
    created_at: datetime


class DocumentDetail(Document):
    versions: list[DocumentVersion] = []


class DownloadUrl(BaseModel):
    url: str
    expires_at: datetime
