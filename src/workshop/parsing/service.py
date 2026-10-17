"""Parsing orchestration: deterministic, no AI."""

from __future__ import annotations

from workshop.document import storage
from workshop.document.models import WorkshopDocumentVersion
from workshop.logging import get_logger
from workshop.parsing.extractors.base import ExtractorError, get_extractor, is_supported
from workshop.parsing.models import ParsedDocument

logger = get_logger(__name__)


def parse_document_version(version: WorkshopDocumentVersion) -> ParsedDocument:
    """Download and parse one document version into source-referenced facts.

    A parse failure is reported on the ParsedDocument; the caller decides whether
    that fails the whole run (only if it was the sole document) or just excludes
    the document.
    """
    if not is_supported(version.mime_type):
        return ParsedDocument(
            document_version_id=version.id,
            features=[],
            parse_failed=True,
            error=f"Unsupported mime type: {version.mime_type}",
        )
    try:
        data = storage.download_bytes(version.storage_key)
        extractor = get_extractor(version.mime_type)
        facts = extractor.extract(data, file_name=version.file_name, document_version_id=version.id)
    except ExtractorError as exc:
        logger.warning("parse.failed", version_id=str(version.id), error=str(exc))
        return ParsedDocument(document_version_id=version.id, features=[], parse_failed=True, error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("parse.error", version_id=str(version.id), error=str(exc))
        return ParsedDocument(document_version_id=version.id, features=[], parse_failed=True, error=str(exc))

    return ParsedDocument(document_version_id=version.id, features=facts)
