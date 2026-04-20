"""Lirox v2.0 — File Generation Engine (backward-compatibility shim)

The document creators have been refactored into the
``lirox.tools.document_creators`` package.  This module re-exports
everything from that package so that existing imports continue to work
without any changes.
"""
from __future__ import annotations

# ── Public re-exports (keep all previous callers working) ─────────────────
from lirox.tools.document_creators import (  # noqa: F401
    create_pdf,
    create_pptx,
    create_docx,
    create_xlsx,
    PALETTES,
    pick_palette as _pick_palette,
    hex_to_rgb as _hex_to_rgb,
    ensure_dep as _ensure_dep,
)

# Legacy aliases (some internal code used the private names)
_logger = __import__("logging").getLogger("lirox.file_generator")

