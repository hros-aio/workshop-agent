"""Scanned image / PDF OCR extraction (Tesseract via pytesseract).

OCR confidence flows into the proposal confidence as a lower bound so a
low-quality scan can never become a high-confidence proposal.
"""

from __future__ import annotations

import io
import uuid

import pytesseract
from PIL import Image

from workshop.parsing.extractors.base import ExtractorError
from workshop.parsing.models import ExtractedFact, SourceRef

_IMAGE_MIME = {"image/png", "image/jpeg", "image/tiff"}


class ImageOcrExtractor:
    def supports(self, mime_type: str) -> bool:
        return mime_type in _IMAGE_MIME

    def extract(self, data: bytes, *, file_name: str, document_version_id: uuid.UUID) -> list[ExtractedFact]:
        try:
            image = Image.open(io.BytesIO(data))
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as exc:
            raise ExtractorError(f"Failed to OCR image: {exc}") from exc

        facts: list[ExtractedFact] = []
        for index, text in enumerate(ocr_data.get("text", [])):
            stripped = text.strip()
            if not stripped:
                continue
            confidence = ocr_data.get("conf", [])[index]
            try:
                score = max(0.0, min(1.0, float(confidence) / 100.0))
            except (TypeError, ValueError):
                score = 0.0
            facts.append(
                ExtractedFact(
                    text=stripped,
                    ocr_confidence=score,
                    source_ref=SourceRef(
                        document_version_id=document_version_id,
                        file_name=file_name,
                        excerpt=stripped[:500],
                    ),
                )
            )
        return facts
