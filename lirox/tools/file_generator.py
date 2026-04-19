"""Lirox v1.1 — File Generation Engine

Actually creates PDF, Word, Excel, and PowerPoint files.
Dependencies are auto-installed on first use.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, List

from lirox.verify import FileReceipt


def _ensure_dep(package: str, import_name: str = None):
    """Auto-install a dependency if missing."""
    import_name = import_name or package.replace("-", "_")
    try:
        return __import__(import_name)
    except ImportError:
        print(f"  [Lirox] Installing {package}…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package, "--quiet",
             "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return __import__(import_name)


def create_pdf(path: str, title: str, sections: List[Dict[str, Any]]) -> FileReceipt:
    """Create a styled PDF report with sections, paragraphs, and bullets."""
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

        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        doc = SimpleDocTemplate(path, pagesize=letter,
                                leftMargin=inch, rightMargin=inch,
                                topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="LiroxTitle", fontSize=22, leading=28,
            textColor=HexColor("#1a1a1a"), spaceAfter=20, fontName="Helvetica-Bold"))
        styles.add(ParagraphStyle(
            name="LiroxH1", fontSize=14, leading=18,
            textColor=HexColor("#2563eb"), spaceAfter=10, spaceBefore=16,
            fontName="Helvetica-Bold"))
        styles.add(ParagraphStyle(
            name="LiroxBody", fontSize=11, leading=15,
            textColor=HexColor("#333333"), spaceAfter=8, fontName="Helvetica"))

        story = [Paragraph(title, styles["LiroxTitle"]), Spacer(1, 12)]

        for sec in sections:
            if sec.get("heading"):
                story.append(Paragraph(sec["heading"], styles["LiroxH1"]))
            if sec.get("body"):
                for para in sec["body"].split("\n\n"):
                    if para.strip():
                        # Escape XML special chars for reportlab
                        safe = para.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        story.append(Paragraph(safe, styles["LiroxBody"]))
            if sec.get("bullets"):
                items = []
                for b in sec["bullets"]:
                    if b and b.strip():
                        safe = b.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        items.append(ListItem(Paragraph(safe, styles["LiroxBody"])))
                if items:
                    story.append(ListFlowable(items, bulletType="bullet", start="•"))
                    story.append(Spacer(1, 6))

        doc.build(story)

        if os.path.exists(path):
            r.ok = True
            r.verified = True
            r.bytes_written = os.path.getsize(path)
            r.message = f"Created PDF: {path} ({r.bytes_written} bytes)"
        else:
            r.error = "PDF build completed but file not found on disk"
        return r
    except Exception as e:
        r.error = f"PDF creation error: {e}"
        return r


def create_docx(path: str, title: str, sections: List[Dict[str, Any]]) -> FileReceipt:
    """Create a Word document with headings, paragraphs, bullets, and tables."""
    r = FileReceipt(tool="file_generator", operation="create_docx", path=path)
    try:
        _ensure_dep("python-docx", "docx")
        from docx import Document
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        doc = Document()

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
                    if b and b.strip():
                        doc.add_paragraph(b.strip(), style="List Bullet")
            if sec.get("table"):
                data = sec["table"]
                if data and len(data) > 0:
                    table = doc.add_table(rows=len(data), cols=len(data[0]))
                    table.style = "Light Grid Accent 1"
                    for i, row_data in enumerate(data):
                        for j, cell_val in enumerate(row_data):
                            table.cell(i, j).text = str(cell_val)

        doc.save(path)

        if os.path.exists(path):
            r.ok = True
            r.verified = True
            r.bytes_written = os.path.getsize(path)
            r.message = f"Created Word doc: {path} ({r.bytes_written} bytes)"
        else:
            r.error = "Word build completed but file not found on disk"
        return r
    except Exception as e:
        r.error = f"Word creation error: {e}"
        return r


def create_xlsx(path: str, title: str, sheets: List[Dict[str, Any]]) -> FileReceipt:
    """Create an Excel workbook with styled headers and data."""
    r = FileReceipt(tool="file_generator", operation="create_xlsx", path=path)
    try:
        _ensure_dep("openpyxl")
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        wb = Workbook()
        wb.remove(wb.active)

        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"))

        for sd in sheets:
            ws = wb.create_sheet(title=str(sd.get("name", "Sheet"))[:31])
            headers = sd.get("headers", [])
            rows = sd.get("rows", [])

            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=str(h))
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
                cell.border = thin_border

            for ri, row_data in enumerate(rows, 2):
                for ci, val in enumerate(row_data, 1):
                    cell = ws.cell(row=ri, column=ci, value=val)
                    cell.border = thin_border

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

        if os.path.exists(path):
            r.ok = True
            r.verified = True
            r.bytes_written = os.path.getsize(path)
            r.message = f"Created Excel: {path} ({r.bytes_written} bytes)"
        else:
            r.error = "Excel build completed but file not found on disk"
        return r
    except Exception as e:
        r.error = f"Excel creation error: {e}"
        return r


def create_pptx(path: str, title: str, slides: List[Dict[str, Any]]) -> FileReceipt:
    """Create a PowerPoint presentation with title slide + content slides."""
    r = FileReceipt(tool="file_generator", operation="create_pptx", path=path)
    try:
        _ensure_dep("python-pptx", "pptx")
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor

        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # Title slide
        title_layout = prs.slide_layouts[0]
        sl0 = prs.slides.add_slide(title_layout)
        sl0.shapes.title.text = title
        try:
            sl0.placeholders[1].text = "Generated by Lirox"
        except (KeyError, IndexError):
            pass

        # Content slides
        content_layout = prs.slide_layouts[1]
        for sd in slides:
            sl = prs.slides.add_slide(content_layout)
            sl.shapes.title.text = sd.get("title", "")

            try:
                body = sl.placeholders[1]
                tf = body.text_frame
                tf.clear()
                bullets = sd.get("bullets", [])
                for i, bullet in enumerate(bullets):
                    if i == 0:
                        tf.paragraphs[0].text = str(bullet)
                        tf.paragraphs[0].font.size = Pt(18)
                    else:
                        p = tf.add_paragraph()
                        p.text = str(bullet)
                        p.font.size = Pt(18)
                        p.level = 0
            except (KeyError, IndexError):
                pass

            if sd.get("notes"):
                try:
                    sl.notes_slide.notes_text_frame.text = sd["notes"]
                except Exception:
                    pass

        prs.save(path)

        if os.path.exists(path):
            r.ok = True
            r.verified = True
            r.bytes_written = os.path.getsize(path)
            r.message = f"Created PowerPoint: {path} ({r.bytes_written} bytes, {len(slides)+1} slides)"
        else:
            r.error = "PowerPoint build completed but file not found on disk"
        return r
    except Exception as e:
        r.error = f"PowerPoint creation error: {e}"
        return r
