"""Tests for real file creation via document_creators.

This module covers a mix of behaviors, including:
  1. Creator functions returning successful receipts.
  2. Files being created on disk, including in nested directories.
  3. Basic receipt metadata such as bytes written or section counts.
  4. Independent FileVerificationEngine checks in dedicated verification tests.
"""
import os

import pytest

from lirox.tools.document_creators import create_pdf, create_pptx, create_docx, create_xlsx
from lirox.verify import FileVerificationEngine


# ── Shared fixture ─────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_dir(tmp_path):
    return str(tmp_path)


# ── PDF ────────────────────────────────────────────────────────────────────

class TestCreatePdf:
    def test_creates_file_on_disk(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.pdf")
        receipt = create_pdf(
            path,
            "Test PDF",
            [{"heading": "Intro", "body": "Body text here.", "bullets": ["Point 1", "Point 2"]}],
            query="test pdf",
            user_name="Tester",
        )
        assert receipt.ok, f"receipt.ok is False: {receipt.error}"
        assert receipt.verified, "receipt.verified is False"
        assert os.path.exists(path), "PDF file not found on disk"
        assert receipt.bytes_written > 0, "bytes_written is 0"

    def test_file_passes_verification(self, tmp_dir):
        path = os.path.join(tmp_dir, "verify.pdf")
        create_pdf(path, "Verify PDF",
                   [{"heading": "S1", "body": "Paragraph.", "bullets": []}])
        result = FileVerificationEngine.verify(path)
        assert result["passed"], f"FileVerificationEngine failed: {result['issues']}"
        assert result["size"] > 0

    def test_multiple_sections(self, tmp_dir):
        path = os.path.join(tmp_dir, "multi.pdf")
        sections = [
            {"heading": f"Section {i}", "body": f"Body text for section {i}.", "bullets": [f"Bullet {i}"]}
            for i in range(1, 6)
        ]
        receipt = create_pdf(path, "Multi-Section PDF", sections, query="test")
        assert receipt.ok
        assert receipt.details.get("section_count") == 5

    def test_creates_parent_directories(self, tmp_dir):
        nested = os.path.join(tmp_dir, "sub", "nested", "doc.pdf")
        receipt = create_pdf(nested, "Nested PDF",
                             [{"heading": "H", "body": "B", "bullets": []}])
        assert receipt.ok
        assert os.path.exists(nested)

    def test_receipt_has_bytes_written(self, tmp_dir):
        path = os.path.join(tmp_dir, "bytes.pdf")
        receipt = create_pdf(path, "Bytes PDF",
                             [{"heading": "H", "body": "Some body text.", "bullets": []}])
        assert receipt.ok
        assert receipt.bytes_written == os.path.getsize(path)


# ── PPTX ───────────────────────────────────────────────────────────────────

class TestCreatePptx:
    _slides = [
        {"title": "Overview", "bullets": ["Point A", "Point B", "Point C"], "notes": "Notes here"},
        {"title": "Details",  "bullets": ["Detail 1", "Detail 2"],          "notes": ""},
    ]

    def test_creates_file_on_disk(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.pptx")
        receipt = create_pptx(path, "Test Deck", self._slides, query="test pptx", user_name="Tester")
        assert receipt.ok, f"receipt.ok is False: {receipt.error}"
        assert receipt.verified
        assert os.path.exists(path)
        assert receipt.bytes_written > 0

    def test_file_passes_verification(self, tmp_dir):
        path = os.path.join(tmp_dir, "verify.pptx")
        create_pptx(path, "Verify Deck", self._slides)
        result = FileVerificationEngine.verify(path)
        assert result["passed"], f"FileVerificationEngine failed: {result['issues']}"

    def test_slide_count_in_details(self, tmp_dir):
        path = os.path.join(tmp_dir, "slides.pptx")
        receipt = create_pptx(path, "Count Deck", self._slides)
        assert receipt.ok
        # Hero + content slides + closing = len(slides) + 2
        assert receipt.details.get("slide_count") == len(self._slides) + 2

    def test_empty_slides_creates_hero_closing(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.pptx")
        receipt = create_pptx(path, "Empty Deck", [])
        assert receipt.ok
        assert os.path.exists(path)


# ── DOCX ───────────────────────────────────────────────────────────────────

class TestCreateDocx:
    _sections = [
        {"heading": "Introduction", "body": "Body paragraph text here.", "bullets": ["Bullet A", "Bullet B"]},
        {"heading": "Conclusion",   "body": "Final paragraph.",           "bullets": []},
    ]

    def test_creates_file_on_disk(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.docx")
        receipt = create_docx(path, "Test Doc", self._sections, query="test docx", user_name="Tester")
        assert receipt.ok, f"receipt.ok is False: {receipt.error}"
        assert receipt.verified
        assert os.path.exists(path)
        assert receipt.bytes_written > 0

    def test_file_passes_verification(self, tmp_dir):
        path = os.path.join(tmp_dir, "verify.docx")
        create_docx(path, "Verify Doc", self._sections)
        result = FileVerificationEngine.verify(path)
        assert result["passed"], f"FileVerificationEngine failed: {result['issues']}"

    def test_section_count_in_details(self, tmp_dir):
        path = os.path.join(tmp_dir, "count.docx")
        receipt = create_docx(path, "Count Doc", self._sections)
        assert receipt.ok
        assert receipt.details.get("section_count") == len(self._sections)

    def test_with_inline_table(self, tmp_dir):
        path = os.path.join(tmp_dir, "table.docx")
        sections = [{"heading": "Data", "body": "See table.", "bullets": [],
                     "table": [["Col1", "Col2"], ["R1C1", "R1C2"]]}]
        receipt = create_docx(path, "Table Doc", sections)
        assert receipt.ok
        assert os.path.exists(path)


# ── XLSX ───────────────────────────────────────────────────────────────────

class TestCreateXlsx:
    _sheets = [
        {"name": "Sales", "headers": ["Month", "Revenue", "Units"],
         "rows": [["Jan", "10000", "50"], ["Feb", "12000", "60"]]},
    ]

    def test_creates_file_on_disk(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.xlsx")
        receipt = create_xlsx(path, "Test Workbook", self._sheets, query="test xlsx", user_name="Tester")
        assert receipt.ok, f"receipt.ok is False: {receipt.error}"
        assert receipt.verified
        assert os.path.exists(path)
        assert receipt.bytes_written > 0

    def test_file_passes_verification(self, tmp_dir):
        path = os.path.join(tmp_dir, "verify.xlsx")
        create_xlsx(path, "Verify WB", self._sheets)
        result = FileVerificationEngine.verify(path)
        assert result["passed"], f"FileVerificationEngine failed: {result['issues']}"

    def test_row_count_in_details(self, tmp_dir):
        path = os.path.join(tmp_dir, "rows.xlsx")
        receipt = create_xlsx(path, "Row WB", self._sheets)
        assert receipt.ok
        assert receipt.details.get("row_count") == 2

    def test_multiple_sheets(self, tmp_dir):
        path = os.path.join(tmp_dir, "multi.xlsx")
        sheets = [
            {"name": "Sheet1", "headers": ["A"], "rows": [["1"]]},
            {"name": "Sheet2", "headers": ["B"], "rows": [["2"], ["3"]]},
        ]
        receipt = create_xlsx(path, "Multi WB", sheets)
        assert receipt.ok
        assert receipt.details.get("sheet_count") == 2
        assert receipt.details.get("row_count") == 3


# ── FileVerificationEngine ────────────────────────────────────────────────

class TestFileVerificationEngine:
    def test_missing_file_fails(self, tmp_dir):
        result = FileVerificationEngine.verify(os.path.join(tmp_dir, "nonexistent.pdf"))
        assert not result["passed"]
        assert result["size"] == 0
        assert result["issues"]

    def test_existing_file_passes(self, tmp_dir):
        path = os.path.join(tmp_dir, "real.pdf")
        receipt = create_pdf(path, "Real PDF",
                             [{"heading": "H", "body": "Body text.", "bullets": []}])
        assert receipt.ok
        result = FileVerificationEngine.verify(path)
        assert result["passed"]

    def test_reports_actual_file_size(self, tmp_dir):
        path = os.path.join(tmp_dir, "size.xlsx")
        receipt = create_xlsx(path, "Size WB",
                              [{"name": "S", "headers": ["X"], "rows": [["1"]]}])
        assert receipt.ok
        result = FileVerificationEngine.verify(path)
        assert result["size"] == os.path.getsize(path)
