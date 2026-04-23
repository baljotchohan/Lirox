"""PDF Creator — Professional Document Engine.

Produces a styled, multi-section PDF with:
  - Topic-aware color palettes
  - Cover page with title, author, and date
  - Table of Contents (when 3+ sections)
  - Accent horizontal rules and callout boxes
  - Page numbers and running header
  - Proper typography (Helvetica / justified body text)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from lirox.verify import FileReceipt
from lirox.tools.document_creators.base import ensure_dep, pick_palette, PALETTES
from lirox.safety.audit import log_audit_event

_logger = logging.getLogger("lirox.document_creators.pdf")


def create_pdf(path: str, title: str, sections: List[Dict[str, Any]],
               query: str = "", user_name: str = "", user_expertise: str = "intermediate",
               design_plan=None) -> FileReceipt:
    """Create a professionally styled PDF.

    Parameters
    ----------
    path:       Absolute output path.
    title:      Document title.
    sections:   List of dicts with keys ``heading``, ``body``, ``bullets``.
    query:      Original user request — used for palette selection.
    user_name:  Shown as author on the cover page.

    Returns
    -------
    FileReceipt with ``ok=True`` and ``verified=True`` on success.
    """
    from pathlib import Path as _Path
    out_path = _Path(path).resolve()
    r = FileReceipt(tool="pdf_creator", operation="create_pdf", path=str(out_path))

    # ── PRE-FLIGHT VALIDATION (v1.1 fix) ──
    if not path:
        r.error = "Path cannot be empty"
        return r
    if not title:
        title = "Untitled Document"
    if user_name is None:
        user_name = ""
    if sections is None or not isinstance(sections, list):
        sections = [{"heading": title, "body": "", "bullets": []}]
    if not sections:
        sections = [{"heading": title, "body": "", "bullets": []}]

    try:
        ensure_dep("reportlab")
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak,
            Table, TableStyle, ListFlowable, ListItem,
            HRFlowable, KeepTogether,
        )

        out_dir = out_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(str(out_dir), os.W_OK):
            r.error = f"Output directory is not writable: {out_dir}"
            return r

        # Use LLM dynamic color scheme if provided, otherwise fallback
        if design_plan and hasattr(design_plan, 'color_scheme') and design_plan.color_scheme:
            pal = design_plan.color_scheme
            palette_name = getattr(design_plan, 'palette', 'custom_llm_palette')
            _logger.info("Using LLM generated color scheme: %s", palette_name)
        elif design_plan and hasattr(design_plan, 'palette'):
            palette_name = design_plan.palette
            _logger.info("Using design plan palette: %s", palette_name)
            pal = PALETTES.get(palette_name, PALETTES.get("default", {}))
        else:
            palette_name = pick_palette(query or title, title, user_expertise=user_expertise)
            _logger.info("Using fallback palette: %s", palette_name)
            pal = PALETTES.get(palette_name, PALETTES.get("default", {}))

        # ── EXTRACT DESIGN THINKING CONTEXT ──
        theme_val = getattr(design_plan.theme, 'value', 'professional') if design_plan and hasattr(design_plan, 'theme') else 'professional'
        style_guide = design_plan.style_guide if design_plan and hasattr(design_plan, 'style_guide') else {}
        typography = design_plan.typography if design_plan and hasattr(design_plan, 'typography') else {}

        # 1. Spacing & Layout
        spacing_level = style_guide.get("spacing", "tight")
        if spacing_level == "generous":
            margin = 1.25 * inch
            body_leading = 18
        else:
            margin = 0.85 * inch
            body_leading = 15

        # 2. Typography Mapping
        req_heading_font = typography.get("heading", "Helvetica").lower()
        if req_heading_font in ["georgia", "times", "serif"]:
            h_font = "Times-Roman"
            h_font_bold = "Times-Bold"
        else:
            h_font = "Helvetica"
            h_font_bold = "Helvetica-Bold"

        req_body_font = typography.get("body", "Helvetica").lower()
        if req_body_font in ["georgia", "times", "serif"]:
            b_font = "Times-Roman"
            b_font_bold = "Times-Bold"
            b_font_it = "Times-Italic"
        else:
            b_font = "Helvetica"
            b_font_bold = "Helvetica-Bold"
            b_font_it = "Helvetica-Oblique"

        h_size = int(typography.get("heading_size", 24))
        b_size = int(typography.get("body_size", 11))
        
        # Determine text color fallback
        text_color = pal.get('text_dark', '333333')

        doc = SimpleDocTemplate(
            str(out_path), pagesize=A4,
            topMargin=margin * 0.8,
            bottomMargin=margin * 0.8,
            leftMargin=margin,
            rightMargin=margin,
            title=title,
            author=user_name or "Generated Document",
        )

        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            "CoverTitle",
            parent=styles["Title"],
            fontName=h_font_bold,
            fontSize=32 if theme_val != 'minimal' else 28,
            textColor=HexColor(f"#{pal['primary']}"),
            spaceAfter=20,
            alignment=TA_LEFT if theme_val != 'corporate' else TA_CENTER,
            leading=38,
        ))
        styles.add(ParagraphStyle(
            "CoverSubtitle",
            parent=styles["Normal"],
            fontName=b_font,
            fontSize=14,
            textColor=HexColor(f"#{pal['accent']}"),
            spaceAfter=6,
            alignment=TA_LEFT if theme_val != 'corporate' else TA_CENTER,
        ))
        styles.add(ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading1"],
            fontName=h_font_bold,
            fontSize=h_size,
            textColor=HexColor(f"#{pal['primary']}"),
            spaceBefore=24,
            spaceAfter=10,
            leading=h_size + 4,
            alignment=TA_LEFT if theme_val != 'minimal' else TA_CENTER,
        ))
        styles.add(ParagraphStyle(
            "BodyText_Custom",
            parent=styles["Normal"],
            fontName=b_font,
            fontSize=b_size,
            leading=body_leading,
            textColor=HexColor(f"#{text_color}"),
            spaceAfter=8,
            alignment=TA_JUSTIFY if theme_val in ['corporate', 'professional'] else TA_LEFT,
        ))
        styles.add(ParagraphStyle(
            "BulletItem",
            parent=styles["Normal"],
            fontName=b_font,
            fontSize=b_size,
            leading=body_leading - 1,
            textColor=HexColor(f"#{text_color}"),
            spaceAfter=4,
            leftIndent=20,
            bulletIndent=10,
        ))
        styles.add(ParagraphStyle(
            "CalloutText",
            parent=styles["Normal"],
            fontName=b_font_it,
            fontSize=b_size,
            textColor=HexColor(f"#{pal['primary']}"),
            leading=body_leading,
            leftIndent=12,
            rightIndent=12,
            spaceBefore=4,
            spaceAfter=4,
        ))

        def _safe(text: str) -> str:
            return (text.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                        .replace("'", "&#39;"))

        def _accent_rule():
            return HRFlowable(
                width="100%", thickness=2,
                color=HexColor(f"#{pal['accent']}"),
                spaceBefore=6, spaceAfter=12,
            )

        def _callout_box(text: str):
            safe = _safe(text)
            data = [[Paragraph(safe, styles["CalloutText"])]]
            t = Table(data, colWidths=[doc.width])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(f"#{pal['secondary']}")),
                ("BOX",        (0, 0), (-1, -1), 1.5, HexColor(f"#{pal['accent']}")),
                ("LEFTPADDING",   (0, 0), (-1, -1), 14),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            return KeepTogether([Spacer(1, 6), t, Spacer(1, 6)])

        from datetime import datetime

        def _add_page_number(canvas_obj, doc_obj):
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 8)
            canvas_obj.setFillColor(HexColor("#999999"))
            canvas_obj.drawCentredString(
                doc_obj.pagesize[0] / 2, 0.4 * inch,
                f"Page {doc_obj.page}")
            if doc_obj.page > 1:
                canvas_obj.setStrokeColor(HexColor(f"#{pal['accent']}"))
                canvas_obj.setLineWidth(0.5)
                canvas_obj.line(
                    0.85 * inch, doc_obj.pagesize[1] - 0.55 * inch,
                    doc_obj.pagesize[0] - 0.85 * inch,
                    doc_obj.pagesize[1] - 0.55 * inch)
                canvas_obj.setFont("Helvetica", 7)
                canvas_obj.setFillColor(HexColor(f"#{pal['primary']}"))
                canvas_obj.drawString(
                    0.85 * inch, doc_obj.pagesize[1] - 0.5 * inch,
                    title[:60])
            canvas_obj.restoreState()

        # ── Cover page ──────────────────────────────────────────────────────
        story = []
        
        # Dynamic Cover Page Layout Based on Theme
        if theme_val == 'creative':
            story.append(Spacer(1, 2 * inch))
            story.append(HRFlowable(width="100%", thickness=12, color=HexColor(f"#{pal['accent']}"), spaceBefore=0, spaceAfter=24, hAlign="LEFT"))
        elif theme_val == 'corporate':
            story.append(Spacer(1, 2.5 * inch))
        else:
            story.append(Spacer(1, 1.5 * inch))
            story.append(HRFlowable(
                width="40%", thickness=3,
                color=HexColor(f"#{pal['primary']}"),
                spaceBefore=0, spaceAfter=12, hAlign="LEFT",
            ))

        story.append(Paragraph(_safe(title), styles["CoverTitle"]))
        story.append(Spacer(1, 8))
        
        author_text = f"Prepared for: {user_name}" if user_name else "Generated Document"
        date_str    = datetime.now().strftime("%B %d, %Y")
        
        story.append(Paragraph(_safe(author_text), styles["CoverSubtitle"]))
        story.append(Paragraph(date_str, styles["CoverSubtitle"]))
        
        if theme_val == 'corporate':
            story.append(Spacer(1, 1 * inch))
            story.append(HRFlowable(width="50%", thickness=1, color=HexColor(f"#{pal['accent']}"), spaceBefore=12, spaceAfter=0, hAlign="CENTER"))
        elif theme_val != 'minimal':
            story.append(Spacer(1, 0.5 * inch))
            story.append(HRFlowable(
                width="100%", thickness=1,
                color=HexColor(f"#{pal['accent']}"),
                spaceBefore=12, spaceAfter=0,
            ))
            
        story.append(PageBreak())

        # ── Table of Contents (3+ sections) ─────────────────────────────────
        if len(sections) >= 3:
            story.append(Paragraph("Table of Contents", styles["SectionHeader"]))
            story.append(_accent_rule())
            for i, sec in enumerate(sections, 1):
                heading = sec.get("heading", f"Section {i}")
                story.append(Paragraph(
                    f"{i}. &nbsp; {_safe(heading)}",
                    styles["BodyText_Custom"]))
            story.append(PageBreak())

        # ── Content sections ─────────────────────────────────────────────────
        for i, sec in enumerate(sections):
            heading = sec.get("heading", "")
            body    = sec.get("body", "")
            bullets = sec.get("bullets", [])

            if heading:
                story.append(Paragraph(_safe(heading), styles["SectionHeader"]))
                # Only add accent rules for non-minimal themes
                if theme_val not in ['minimal']:
                    story.append(_accent_rule())

            if body:
                for para in body.split("\n\n"):
                    if para.strip():
                        story.append(Paragraph(_safe(para.strip()), styles["BodyText_Custom"]))

            if bullets:
                items = [
                    ListItem(
                        Paragraph(_safe(b.strip()), styles["BulletItem"]),
                        bulletColor=HexColor(f"#{pal['primary']}"),
                    )
                    for b in bullets if b and b.strip()
                ]
                if items:
                    bullet_type = "bullet" if theme_val != 'minimal' else "1"
                    bullet_start = "●" if theme_val != 'minimal' else "-"
                    story.append(ListFlowable(items, bulletType=bullet_type, start=bullet_start,
                                              bulletFontSize=8 if theme_val != 'minimal' else 11))
                    story.append(Spacer(1, 8))

            if bullets and theme_val != 'minimal':
                # Use callouts intelligently based on theme/audience
                if (theme_val in ['educational', 'creative']) or (i % 2 == 0):
                    story.append(_callout_box(f"Key Point: {bullets[0][:200]}"))

            story.append(Spacer(1, 12))

        doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)

        if out_path.exists():
            r.ok = True
            r.verified = True
            r.bytes_written = out_path.stat().st_size
            r.message = (
                f"Created PDF: {out_path} "
                f"({r.bytes_written:,} bytes, {len(sections)} sections, "
                f"palette: {palette_name})"
            )
            r.details["section_count"] = len(sections)
            r.details["palette"] = palette_name
        else:
            r.error = "PDF build completed but file not found on disk"
        log_audit_event(
            "document_create_pdf",
            str(out_path),
            status="ok" if (r.ok and r.verified) else "error",
            detail=r.message or r.error,
        )
        return r
    except Exception as e:
        r.error = f"PDF creation error: {e}"
        log_audit_event("document_create_pdf", str(out_path), status="error", detail=r.error)
        return r
