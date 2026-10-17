"""Common extraction model: every fact carries a source reference."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    document_version_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    file_name: str
    document_type: str | None = None
    page: int | None = None
    sheet: str | None = None
    row: int | None = None
    cell: str | None = None
    excerpt: str | None = None


class ExtractedFact(BaseModel):
    text: str
    source_ref: SourceRef
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ParsedDocument(BaseModel):
    document_version_id: uuid.UUID
    features: list[ExtractedFact]
    parse_failed: bool = False
    error: str | None = None
