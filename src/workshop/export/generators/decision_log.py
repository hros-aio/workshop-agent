"""Decision Log: every decision, chronological, across all rounds."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from workshop.export.templates import DECISION_LOG_FILE

_HEADERS = [
    "Round",
    "Entity Type",
    "Entity Key",
    "Action",
    "Resulting Value",
    "Comment",
    "Decided By",
    "Decided At",
    "Reopened",
]


def generate_decision_log(rows: list[dict[str, Any]]) -> tuple[str, bytes]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Decisions"
    sheet.append(_HEADERS)

    for row in rows:
        sheet.append(
            [
                row.get("round_number"),
                row.get("entity_type"),
                row.get("entity_key"),
                row.get("action"),
                str(row.get("resulting_value")),
                row.get("comment") or "",
                str(row.get("decided_by")),
                row["decided_at"].isoformat() if row.get("decided_at") else "",
                "Yes" if row.get("reopened") else "No",
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    return DECISION_LOG_FILE, buffer.getvalue()
