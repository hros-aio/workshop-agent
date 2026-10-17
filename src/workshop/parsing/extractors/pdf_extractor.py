"""PDF extraction with page-level source references (pdfplumber)."""

from __future__ import annotations

import io
import uuid

import pdfplumber

from workshop.parsing.extractors.base import ExtractorError
from workshop.parsing.models import ExtractedFact, SourceRef


class PdfExtractor:
    def supports(self, mime_type: str) -> bool:
        return mime_type == "application/pdf"

    def extract(self, data: bytes, *, file_name: str, document_version_id: uuid.UUID) -> list[ExtractedFact]:
        facts: list[ExtractedFact] = []
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    for line in text.splitlines():
                        stripped = line.strip()
                        if not stripped:
                            continue
                        facts.append(
                            ExtractedFact(
                                text=stripped,
                                source_ref=SourceRef(
                                    document_version_id=document_version_id,
                                    file_name=file_name,
                                    page=page_number,
                                    excerpt=stripped[:500],
                                ),
                            )
                        )
                    for table in page.extract_tables():
                        for row_index, row in enumerate(table, start=1):
                            cells = ["" if c is None else str(c) for c in row]
                            text = " | ".join(cells).strip()
                            if text:
                                facts.append(
                                    ExtractedFact(
                                        text=text,
                                        source_ref=SourceRef(
                                            document_version_id=document_version_id,
                                            file_name=file_name,
                                            page=page_number,
                                            row=row_index,
                                            excerpt=text[:500],
                                        ),
                                    )
                                )
        except Exception as exc:
            raise ExtractorError(f"Failed to parse PDF: {exc}") from exc
        return facts
