"""Lirox v2.0.0 — File Operations

BUG-3 FIX: PDF creation now uses fpdf2 for real PDFs (not plain text renamed .pdf).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from lirox.config import SAFE_DIRS_RESOLVED, PROTECTED_PATHS, OUTPUTS_DIR


# ─── Safety Helpers ───────────────────────────────────────────────────────────

def _is_safe_path(path: str) -> bool:
    """Check that the resolved path is inside a safe directory."""
    try:
        resolved = str(Path(path).expanduser().resolve())
    except Exception:
        return False
    for protected in PROTECTED_PATHS:
        if resolved.startswith(protected):
            return False
    for safe in SAFE_DIRS_RESOLVED:
        if resolved == safe or resolved.startswith(safe + os.sep):
            return True
    return False


# ─── Core File Operations ─────────────────────────────────────────────────────

def read_file(path: str, max_bytes: int = 50000) -> str:
    """Read a text file. Returns content or an error string."""
    expanded = str(Path(path).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{path}' is outside safe directories."
    if not os.path.exists(expanded):
        return f"Error: File not found: {path}"
    if not os.path.isfile(expanded):
        return f"Error: Not a file: {path}"
    try:
        size = os.path.getsize(expanded)
        if size > max_bytes:
            with open(expanded, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return content + f"\n\n[Truncated — file is {size:,} bytes, showing first {max_bytes:,}]"
        with open(expanded, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    expanded = str(Path(path).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{path}' is outside safe directories."
    try:
        parent = Path(expanded).parent
        parent.mkdir(parents=True, exist_ok=True)
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written: {path} ({len(content):,} chars)"
    except Exception as e:
        return f"Error writing file: {e}"


def create_file(path: str, content: str = "") -> str:
    """Create a new file (fails if file already exists)."""
    expanded = str(Path(path).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{path}' is outside safe directories."
    if os.path.exists(expanded):
        return f"Error: File already exists: {path}"
    return write_file(path, content)


def delete_file(path: str) -> str:
    """Delete a file."""
    expanded = str(Path(path).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{path}' is outside safe directories."
    if not os.path.exists(expanded):
        return f"Error: File not found: {path}"
    try:
        os.remove(expanded)
        return f"Deleted: {path}"
    except Exception as e:
        return f"Error deleting file: {e}"


def list_files(path: str = ".", max_items: int = 100) -> str:
    """List files in a directory."""
    expanded = str(Path(path).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{path}' is outside safe directories."
    if not os.path.exists(expanded):
        return f"Error: Path not found: {path}"
    if not os.path.isdir(expanded):
        return f"Error: Not a directory: {path}"
    try:
        items = sorted(os.listdir(expanded))
        if len(items) > max_items:
            items = items[:max_items]
            truncated = True
        else:
            truncated = False
        lines = []
        for item in items:
            full_path = os.path.join(expanded, item)
            if os.path.isdir(full_path):
                lines.append(f"  📁 {item}/")
            else:
                size = os.path.getsize(full_path)
                lines.append(f"  📄 {item} ({size:,} bytes)")
        result = f"Directory: {path}\n" + "\n".join(lines)
        if truncated:
            result += f"\n  ... (showing first {max_items} items)"
        return result
    except Exception as e:
        return f"Error listing directory: {e}"


def copy_file(src: str, dst: str) -> str:
    """Copy a file from src to dst."""
    src_exp = str(Path(src).expanduser())
    dst_exp = str(Path(dst).expanduser())
    for p in (src_exp, dst_exp):
        if not _is_safe_path(p):
            return f"Error: Path '{p}' is outside safe directories."
    if not os.path.exists(src_exp):
        return f"Error: Source not found: {src}"
    try:
        Path(dst_exp).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_exp, dst_exp)
        return f"Copied: {src} → {dst}"
    except Exception as e:
        return f"Error copying: {e}"


def append_to_file(path: str, content: str) -> str:
    """Append content to an existing file."""
    expanded = str(Path(path).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{path}' is outside safe directories."
    try:
        Path(expanded).parent.mkdir(parents=True, exist_ok=True)
        with open(expanded, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content):,} chars to: {path}"
    except Exception as e:
        return f"Error appending: {e}"


# ─── PDF Creation (BUG-3 FIX) ────────────────────────────────────────────────

def create_pdf(filename: str, content: str, title: str = "") -> str:
    """
    Create a real PDF file using fpdf2.
    BUG-3 FIX: Uses fpdf2 instead of renaming a .txt file to .pdf.
    Falls back to plain text if fpdf2 is not installed.
    """
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    # Ensure output goes to OUTPUTS_DIR if no directory specified
    path = Path(filename)
    if not path.is_absolute() and str(path.parent) == ".":
        filename = os.path.join(OUTPUTS_DIR, path.name)

    expanded = str(Path(filename).expanduser())
    if not _is_safe_path(expanded):
        return f"Error: Path '{filename}' is outside safe directories."

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title
        if title:
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, title, ln=True, align="C")
            pdf.ln(5)

        # Body
        pdf.set_font("Helvetica", size=12)
        for line in content.split("\n"):
            if line.startswith("# "):
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 8, line[2:], ln=True)
                pdf.set_font("Helvetica", size=12)
            elif line.startswith("## "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 7, line[3:], ln=True)
                pdf.set_font("Helvetica", size=12)
            else:
                pdf.multi_cell(0, 6, line or " ")

        Path(expanded).parent.mkdir(parents=True, exist_ok=True)
        pdf.output(expanded)
        return f"PDF created: {expanded}"

    except ImportError:
        # Fallback: write plain text with .pdf extension
        try:
            Path(expanded).parent.mkdir(parents=True, exist_ok=True)
            with open(expanded, "w", encoding="utf-8") as f:
                if title:
                    f.write(f"{title}\n{'='*len(title)}\n\n")
                f.write(content)
            return (
                f"Created text file: {expanded}\n"
                "(fpdf2 not installed — install with: pip install fpdf2)"
            )
        except Exception as e:
            return f"Error creating file: {e}"
    except Exception as e:
        return f"Error creating PDF: {e}"
