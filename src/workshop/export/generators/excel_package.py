"""Entity workbook generator (template-exact, in-scope only)."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from workshop.export.templates import (
    PROVENANCE_COLUMNS,
    TemplateSpec,
    template_for,
)


def _source_reference(source_refs: list[dict[str, Any]]) -> str:
    if not source_refs:
        return ""
    ref = source_refs[0]
    parts: list[str] = []
    if ref.get("page") is not None:
        parts.append(f"page {ref['page']}")
    if ref.get("sheet"):
        parts.append(f"sheet {ref['sheet']}")
    if ref.get("row") is not None:
        parts.append(f"row {ref['row']}")
    if ref.get("cell"):
        parts.append(f"cell {ref['cell']}")
    return ", ".join(parts)


def _provenance_values(row: dict[str, Any]) -> list[Any]:
    source_refs = row.get("source_refs") or []
    document = source_refs[0].get("file_name", "") if source_refs else ""
    approved_by = row.get("decided_by")
    return [document, _source_reference(source_refs), str(approved_by) if approved_by else ""]


def build_workbook_bytes(
    spec: TemplateSpec,
    rows: list[dict[str, Any]],
    *,
    include_provenance: bool = True,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Import"

    headers = [header for header, _field in spec.columns]
    if include_provenance:
        headers += [header for header, _field in PROVENANCE_COLUMNS]
    sheet.append(headers)

    for row in rows:
        value = row["resulting_value"]
        values = [value.get(field) for _header, field in spec.columns]
        if include_provenance:
            values += _provenance_values(row)
        sheet.append(values)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def generate_entity_workbooks(dataset: list[dict[str, Any]], scoped_entity_types: list[str]) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    for entity_type in scoped_entity_types:
        spec = template_for(entity_type)
        rows = [row for row in dataset if row["entity_type"] == entity_type]
        artifacts[spec.file_name] = build_workbook_bytes(spec, rows)
    return artifacts
