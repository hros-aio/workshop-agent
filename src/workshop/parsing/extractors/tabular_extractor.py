"""CSV and Excel extraction (deterministic; pandas + openpyxl, dtype=str)."""

from __future__ import annotations

import io
import uuid

import pandas as pd

from workshop.parsing.extractors.base import ExtractorError
from workshop.parsing.models import ExtractedFact, SourceRef

_CSV_MIME = {"text/csv"}
_XLSX_MIME = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}


class TabularExtractor:
    def supports(self, mime_type: str) -> bool:
        return mime_type in _CSV_MIME | _XLSX_MIME

    def extract(self, data: bytes, *, file_name: str, document_version_id: uuid.UUID) -> list[ExtractedFact]:
        if file_name.lower().endswith(".csv") or file_name.lower().endswith(".txt"):
            return self._extract_csv(data, file_name, document_version_id)
        return self._extract_excel(data, file_name, document_version_id)

    def _row_fact(
        self,
        *,
        file_name: str,
        document_version_id: uuid.UUID,
        row: int,
        sheet: str | None,
        record: dict[str, str],
    ) -> ExtractedFact:
        text = "; ".join(f"{k}={v}" for k, v in record.items() if v not in (None, "", "nan"))
        return ExtractedFact(
            text=text,
            source_ref=SourceRef(
                document_version_id=document_version_id,
                file_name=file_name,
                sheet=sheet,
                row=row,
                excerpt=text[:500],
            ),
        )

    def _extract_csv(self, data: bytes, file_name: str, document_version_id: uuid.UUID) -> list[ExtractedFact]:
        try:
            frame = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
        except Exception as exc:  # pragma: no cover - defensive
            raise ExtractorError(f"Failed to parse CSV: {exc}") from exc
        return self._frame_facts(frame, file_name, document_version_id, sheet=None)

    def _extract_excel(self, data: bytes, file_name: str, document_version_id: uuid.UUID) -> list[ExtractedFact]:
        try:
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=str, keep_default_na=False)
        except Exception as exc:
            raise ExtractorError(f"Failed to parse Excel: {exc}") from exc
        facts: list[ExtractedFact] = []
        for sheet_name, frame in sheets.items():
            facts.extend(self._frame_facts(frame, file_name, document_version_id, sheet=str(sheet_name)))
        return facts

    def _frame_facts(
        self,
        frame: pd.DataFrame,
        file_name: str,
        document_version_id: uuid.UUID,
        *,
        sheet: str | None,
    ) -> list[ExtractedFact]:
        columns = [str(c) for c in frame.columns]
        facts: list[ExtractedFact] = []
        for index, row in frame.iterrows():
            record = {columns[i]: str(row.iloc[i]) for i in range(len(columns))}
            # Row numbers are 1-based, +1 to account for the header row.
            facts.append(
                self._row_fact(
                    file_name=file_name,
                    document_version_id=document_version_id,
                    row=int(index) + 2,
                    sheet=sheet,
                    record=record,
                )
            )
        return facts
