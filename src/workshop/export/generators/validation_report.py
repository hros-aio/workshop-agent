"""Validation Report: the latest passing run's per-rule results."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from workshop.export.templates import VALIDATION_REPORT_FILE

_HEADERS = ["Rule", "Result", "Failing Records"]


def generate_validation_report(run: Any, results: list[Any]) -> tuple[str, bytes]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Validation"
    sheet.append(_HEADERS)

    for result in results:
        failing = result.failing_records or []
        sheet.append(
            [
                result.rule_code,
                result.result,
                "; ".join(str(record) for record in failing),
            ]
        )

    sheet.append([])
    sheet.append(["Overall", run.overall_result, f"Round {run.round_number}"])

    buffer = BytesIO()
    workbook.save(buffer)
    return VALIDATION_REPORT_FILE, buffer.getvalue()
