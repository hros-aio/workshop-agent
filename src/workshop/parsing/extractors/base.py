"""Extractor interface and factory.

Every extractor returns `ExtractedFact[]` with source references. The analysis
module never branches on file type: it calls the factory and gets facts.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from workshop.parsing.models import ExtractedFact


class Extractor(Protocol):
    def supports(self, mime_type: str) -> bool: ...

    def extract(self, data: bytes, *, file_name: str, document_version_id: uuid.UUID) -> list[ExtractedFact]: ...


class ExtractorError(Exception):
    """Raised when a document cannot be parsed."""


_SUPPORTED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "text/plain",
}


def is_supported(mime_type: str) -> bool:
    return mime_type in _SUPPORTED_MIME


def get_extractor(mime_type: str) -> Extractor:
    """Resolve an extractor for a mime type. Imports are local to keep the
    optional heavy parsing dependencies out of module import time."""
    from workshop.parsing.extractors.docx_extractor import DocxExtractor
    from workshop.parsing.extractors.image_ocr_extractor import ImageOcrExtractor
    from workshop.parsing.extractors.pdf_extractor import PdfExtractor
    from workshop.parsing.extractors.tabular_extractor import TabularExtractor

    extractors: list[Extractor] = [
        PdfExtractor(),
        DocxExtractor(),
        TabularExtractor(),
        ImageOcrExtractor(),
    ]
    for extractor in extractors:
        if extractor.supports(mime_type):
            return extractor
    raise ExtractorError(f"Unsupported mime type: {mime_type}")
