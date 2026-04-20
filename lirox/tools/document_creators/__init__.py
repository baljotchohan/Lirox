"""lirox.tools.document_creators

Modular document creation engine for Lirox v2.0.

Exports four creator functions (one per format) plus the shared design
system from ``base``.  All functions return a ``FileReceipt`` so callers
can verify the file was actually written to disk before reporting success.
"""
from lirox.tools.document_creators.pdf_creator  import create_pdf
from lirox.tools.document_creators.pptx_creator import create_pptx
from lirox.tools.document_creators.docx_creator import create_docx
from lirox.tools.document_creators.xlsx_creator import create_xlsx
from lirox.tools.document_creators.base import (
    PALETTES,
    pick_palette,
    hex_to_rgb,
    ensure_dep,
)

__all__ = [
    "create_pdf",
    "create_pptx",
    "create_docx",
    "create_xlsx",
    "PALETTES",
    "pick_palette",
    "hex_to_rgb",
    "ensure_dep",
]
