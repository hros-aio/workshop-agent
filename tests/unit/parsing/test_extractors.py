"""Unit tests for deterministic extractors (dtype=str, source references)."""

from __future__ import annotations

import io
import uuid

import openpyxl
import pytest

from workshop.parsing.extractors.tabular_extractor import TabularExtractor


def test_csv_preserves_leading_zero_codes() -> None:
    data = b"company_code;name\n00123;Acme\n"
    facts = TabularExtractor().extract(data, file_name="companies.csv", document_version_id=uuid.uuid4())
    assert len(facts) == 1
    assert "00123" in facts[0].text
    assert facts[0].source_ref.row == 2


def test_excel_multisheet_source_references() -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Departments"
    sheet.append(["code", "name"])
    sheet.append(["D1", "Finance"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    facts = TabularExtractor().extract(
        buffer.getvalue(),
        file_name="org.xlsx",
        document_version_id=uuid.uuid4(),
    )
    assert len(facts) == 1
    assert facts[0].source_ref.sheet == "Departments"
    assert facts[0].source_ref.row == 2
    assert facts[0].source_ref.cell is None
    assert "Finance" in facts[0].text


def test_docx_extraction_paragraphs_and_tables() -> None:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Company policy excerpt")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Location"
    table.rows[0].cells[1].text = "Berlin"
    buffer = io.BytesIO()
    document.save(buffer)

    from workshop.parsing.extractors.docx_extractor import DocxExtractor

    facts = DocxExtractor().extract(buffer.getvalue(), file_name="policy.docx", document_version_id=uuid.uuid4())
    texts = [f.text for f in facts]
    assert any("Company policy excerpt" in t for t in texts)
    assert any("Berlin" in t for t in texts)
    assert all(f.source_ref.file_name == "policy.docx" for f in facts)
