"""Lirox v3.1 — File Generation Engine

Generates PDF, Word (.docx), Excel (.xlsx), and PowerPoint (.pptx) files
from structured data provided by the LLM planner.

Dependencies (installed on first use):
  - reportlab     (PDF)
  - python-docx   (Word)
  - openpyxl      (Excel)
  - python-pptx   (PowerPoint)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.verify import FileReceipt


def _ensure_dep(package: str, import_name: str = None):
    """Install a dependency if missing. Returns the imported module."""
    import_name = import_name or package
    try:
        return __import__(import_name)
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package, "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return __import__(import_name)


def create_pdf(path: str, title: str, sections: List[Dict[str, Any]]) -> FileReceipt:
    """Create a PDF report.

    sections: [{"heading": "...", "body": "...", "bullets": ["...", ...]}]
    """
    r = FileReceipt(tool="file_generator", operation="create_pdf", path=path)
    try:
        _ensure_dep("reportlab")
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
        )

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        doc = SimpleDocTemplate(path, pagesize=letter,
                                leftMargin=inch, rightMargin=inch,
                                topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="LiroxTitle", fontSize=22, leading=28,
            textColor=HexColor("#1a1a1a"), spaceAfter=20,
            fontName="Helvetica-Bold",
        ))
        styles.add(ParagraphStyle(
            name="LiroxHeading", fontSize=14, leading=18,
            textColor=HexColor("#2563eb"), spaceAfter=10, spaceBefore=16,
            fontName="Helvetica-Bold",
        ))
        styles.add(ParagraphStyle(
            name="LiroxBody", fontSize=11, leading=15,
            textColor=HexColor("#333333"), spaceAfter=8,
            fontName="Helvetica",
        ))

        story = []
        story.append(Paragraph(title, styles["LiroxTitle"]))
        story.append(Spacer(1, 12))

        for sec in sections:
            if sec.get("heading"):
                story.append(Paragraph(sec["heading"], styles["LiroxHeading"]))
            if sec.get("body"):
                for para in sec["body"].split("\n\n"):
                    if para.strip():
                        story.append(Paragraph(para.strip(), styles["LiroxBody"]))
            if sec.get("bullets"):
                items = [
                    ListItem(Paragraph(b, styles["LiroxBody"]))
                    for b in sec["bullets"] if b.strip()
                ]
                if items:
                    story.append(ListFlowable(items, bulletType="bullet", start="•"))
                    story.append(Spacer(1, 6))

        doc.build(story)
        r.ok = True
        r.verified = os.path.exists(path)
        r.bytes_written = os.path.getsize(path)
        r.message = f"Created PDF: {path} ({r.bytes_written} bytes)"
        return r
    except Exception as e:
        r.error = f"PDF creation error: {e}"
        return r


def create_docx(path: str, title: str, sections: List[Dict[str, Any]]) -> FileReceipt:
    """Create a Word document.

    sections: [{"heading": "...", "body": "...", "bullets": ["..."]}]
    """
    r = FileReceipt(tool="file_generator", operation="create_docx", path=path)
    try:
        _ensure_dep("python-docx", "docx")
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        doc = Document()

        # Style the title
        t = doc.add_heading(title, level=0)
        t.alignment = WD_ALIGN_PARAGRAPH.CENTER

        for sec in sections:
            if sec.get("heading"):
                doc.add_heading(sec["heading"], level=1)
            if sec.get("body"):
                for para in sec["body"].split("\n\n"):
                    if para.strip():
                        doc.add_paragraph(para.strip())
            if sec.get("bullets"):
                for b in sec["bullets"]:
                    if b.strip():
                        doc.add_paragraph(b.strip(), style="List Bullet")
            if sec.get("table"):
                data = sec["table"]  # list of lists
                if data:
                    table = doc.add_table(rows=len(data), cols=len(data[0]))
                    table.style = "Light Grid Accent 1"
                    for i, row_data in enumerate(data):
                        for j, cell_val in enumerate(row_data):
                            table.cell(i, j).text = str(cell_val)

        doc.save(path)
        r.ok = True
        r.verified = os.path.exists(path)
        r.bytes_written = os.path.getsize(path)
        r.message = f"Created Word doc: {path} ({r.bytes_written} bytes)"
        return r
    except Exception as e:
        r.error = f"Word creation error: {e}"
        return r


def create_xlsx(path: str, title: str, sheets: List[Dict[str, Any]]) -> FileReceipt:
    """Create an Excel workbook.

    sheets: [{"name": "Sheet1", "headers": ["A","B"], "rows": [[1,2],[3,4]]}]
    """
    r = FileReceipt(tool="file_generator", operation="create_xlsx", path=path)
    try:
        _ensure_dep("openpyxl")
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        wb = Workbook()
        wb.remove(wb.active)  # remove default sheet

        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        for sheet_data in sheets:
            ws = wb.create_sheet(title=sheet_data.get("name", "Sheet")[:31])
            headers = sheet_data.get("headers", [])
            rows = sheet_data.get("rows", [])

            # Write headers
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
                cell.border = thin_border

            # Write data rows
            for row_idx, row_data in enumerate(rows, 2):
                for col_idx, val in enumerate(row_data, 1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = thin_border

            # Auto-width columns
            for col in ws.columns:
                max_len = 0
                for cell in col:
                    try:
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    except Exception:
                        pass
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

        wb.save(path)
        r.ok = True
        r.verified = os.path.exists(path)
        r.bytes_written = os.path.getsize(path)
        r.message = f"Created Excel: {path} ({r.bytes_written} bytes)"
        return r
    except Exception as e:
        r.error = f"Excel creation error: {e}"
        return r


def create_pptx(path: str, title: str, slides: List[Dict[str, Any]]) -> FileReceipt:
    """Create a PowerPoint presentation.

    slides: [{"title": "...", "bullets": ["..."], "notes": "..."}]
    """
    r = FileReceipt(tool="file_generator", operation="create_pptx", path=path)
    try:
        _ensure_dep("python-pptx", "pptx")
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # Title slide
        title_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_layout)
        slide.shapes.title.text = title
        if slide.placeholders[1]:
            slide.placeholders[1].text = "Generated by Lirox"

        # Content slides
        bullet_layout = prs.slide_layouts[1]
        for s in slides:
            sl = prs.slides.add_slide(bullet_layout)
            sl.shapes.title.text = s.get("title", "")
            body = sl.placeholders[1]
            tf = body.text_frame
            tf.clear()
            for i, bullet in enumerate(s.get("bullets", [])):
                if i == 0:
                    tf.paragraphs[0].text = bullet
                else:
                    p = tf.add_paragraph()
                    p.text = bullet
                    p.level = 0
            # Speaker notes
            if s.get("notes"):
                sl.notes_slide.notes_text_frame.text = s["notes"]

        prs.save(path)
        r.ok = True
        r.verified = os.path.exists(path)
        r.bytes_written = os.path.getsize(path)
        r.message = f"Created PowerPoint: {path} ({r.bytes_written} bytes)"
        return r
    except Exception as e:
        r.error = f"PowerPoint creation error: {e}"
        return r
