"""Lirox v1.1 — RAG extractors.

Adds proper PDF + DOCX text extraction to the existing ingest pipeline.
Drop this file in alongside ingest.py and store.py.

This module is intentionally library-light:
  - PDF via pypdf
  - DOCX via python-docx
  - Everything else returns None (let ingest.py's existing text reader handle it)

If a library is missing, the extractor logs a warning and returns None.
The file is skipped — never silently truncated, never garbage in index.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("lirox.rag.extractors")

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".next", "dist", "build", ".cache", ".pytest_cache",
    "target", ".idea", ".vscode", ".lirox", "egg-info",
}

PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
RICH_EXTS = PDF_EXTS | DOCX_EXTS


def is_skippable_dir(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def too_large(path: Path) -> bool:
    try:
        return path.stat().st_size > MAX_FILE_BYTES
    except OSError:
        return True


def is_rich_format(path: Path) -> bool:
    return path.suffix.lower() in RICH_EXTS


def extract_rich(path: Path) -> Optional[str]:
    """Extract text from PDF or DOCX. Returns None for unsupported / failed."""
    if not path.is_file() or is_skippable_dir(path) or too_large(path):
        return None
    ext = path.suffix.lower()
    try:
        if ext in PDF_EXTS:
            return _read_pdf(path)
        if ext in DOCX_EXTS:
            return _read_docx(path)
    except Exception as exc:
        _logger.warning("Extract failed for %s: %s", path, exc)
        return None
    return None


def _read_pdf(path: Path) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        _logger.warning("pypdf not installed — skipping PDF: %s", path)
        return None
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        _logger.warning("PDF open failed for %s: %s", path, exc)
        return None
    parts = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
        except Exception:
            continue
    text = "\n\n".join(parts).strip()
    return text or None


def _read_docx(path: Path) -> Optional[str]:
    try:
        from docx import Document
    except ImportError:
        _logger.warning("python-docx not installed — skipping DOCX: %s", path)
        return None
    try:
        doc = Document(str(path))
    except Exception as exc:
        _logger.warning("DOCX open failed for %s: %s", path, exc)
        return None
    text = "\n".join(p.text for p in doc.paragraphs).strip()
    return text or None
