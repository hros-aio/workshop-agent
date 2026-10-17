"""Difference Report: final (accepted) value vs original source value."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from workshop.export.templates import DIFFERENCE_REPORT_FILE

_HEADERS = [
    "Entity Type",
    "Entity Key",
    "Field",
    "Original Value",
    "Final Value",
    "Changed",
    "Is Assumption",
    "Source Document",
    "Approved By",
]


def _original_value(source_refs: list[dict[str, Any]]) -> str:
    if not source_refs:
        return ""
    return source_refs[0].get("excerpt") or ""


def generate_difference_report(dataset: list[dict[str, Any]]) -> tuple[str, bytes]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Differences"
    sheet.append(_HEADERS)

    for row in dataset:
        value = row["resulting_value"]
        source_refs = row.get("source_refs") or []
        document = source_refs[0].get("file_name", "") if source_refs else ""
        approved_by = row.get("decided_by")
        for field, final_value in sorted(value.items()):
            if str(field).startswith("_"):
                continue
            original = _original_value(source_refs)
            sheet.append(
                [
                    row["entity_type"],
                    row["entity_key"],
                    field,
                    original,
                    final_value if not isinstance(final_value, (dict, list)) else str(final_value),
                    "Yes" if str(original) != str(final_value) else "No",
                    "Yes" if row.get("is_assumption") else "No",
                    document,
                    str(approved_by) if approved_by else "",
                ]
            )

    buffer = BytesIO()
    workbook.save(buffer)
    return DIFFERENCE_REPORT_FILE, buffer.getvalue()
