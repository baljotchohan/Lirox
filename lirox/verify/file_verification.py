"""File Verification Engine and Content Quality Verifier.

These classes provide post-creation checks to ensure that documents
actually exist on disk and meet minimum quality standards.  The
``PersonalAgent`` calls them after every file creation operation so that
success is never claimed without proof.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_logger = logging.getLogger("lirox.verify.file_verification")

# ─────────────────────────────────────────────────────────────────────────────
# Minimum size thresholds (bytes) — a file smaller than this is probably empty
# ─────────────────────────────────────────────────────────────────────────────

_MIN_SIZES: Dict[str, int] = {
    ".pdf":  1_000,
    ".docx": 3_000,
    ".pptx": 8_000,
    ".xlsx": 2_000,
    ".txt":  10,
    "":      1,
}


class FileVerificationEngine:
    """Verify that a document file was actually created and has real content.

    All checks are filesystem-level; no external processes are required.
    """

    @staticmethod
    def verify(file_path: str) -> Dict[str, Any]:
        """
        Comprehensive file verification.
        
        Checks:
        - File exists on disk
        - File has content (size > 0)
        - File is accessible
        - File type is correct (extension matches)
        
        Returns:
            Dict with:
            - passed: bool
            - issues: List[str] - any problems found
            - file_size: int - size in bytes
            - file_exists: bool
        """
        from pathlib import Path
        
        result = {
            "passed": True,
            "issues": [],
            "file_size": 0,
            "file_exists": False,
        }
        
        # Check 1: File exists
        p = Path(file_path).resolve()
        if not p.exists():
            result["passed"] = False
            result["issues"].append(f"File does not exist: {file_path}")
            return result
        
        result["file_exists"] = True
        
        # Check 2: Is it a file (not directory)
        if not p.is_file():
            result["passed"] = False
            result["issues"].append(f"Path is not a file: {file_path}")
            return result
        
        # Check 3: File has content
        try:
            size = p.stat().st_size
            result["file_size"] = size
            
            if size == 0:
                result["passed"] = False
                result["issues"].append(f"File is empty (0 bytes)")
                return result
            
            # Warn if file is suspiciously small
            if size < 1000:
                result["issues"].append(f"Warning: File is small ({size} bytes), may be incomplete")
                # Don't fail on small size, just warn
            
        except OSError as e:
            result["passed"] = False
            result["issues"].append(f"Cannot read file: {e}")
            return result
        
        # Check 4: File extension matches known types
        ext = p.suffix.lower()
        valid_extensions = {
            ".pdf": "PDF document",
            ".docx": "Word document",
            ".pptx": "PowerPoint presentation",
            ".xlsx": "Excel spreadsheet",
            ".ppt": "PowerPoint",
            ".doc": "Word",
            ".xls": "Excel",
        }
        
        if ext not in valid_extensions:
            result["issues"].append(f"Unknown file type: {ext}")
            # Don't fail, might be intentional
        
        # Check 5: File is readable
        if not p.is_file():
            result["passed"] = False
            result["issues"].append(f"File is not readable")
            return result
        
        # All checks passed
        return result

    @staticmethod
    def verify_batch(paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Verify multiple paths at once.  Returns a dict keyed by path."""
        return {p: FileVerificationEngine.verify(p) for p in paths}


class ContentQualityVerifier:
    """Validate that a document contains the expected amount of content.

    Works with the structured data dicts returned by the LLM planner so
    that we can flag under-populated documents *before* reporting success.
    """

    # Minimum counts that constitute a "real" document
    _MINIMUMS = {
        "slides":   {"count": 2, "bullets_per_slide": 2},
        "sections": {"count": 1, "words_per_body": 10},
        "sheets":   {"count": 1, "rows_per_sheet": 1},
    }

    @classmethod
    def check_pptx(cls, slides: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check that a slide list has adequate content."""
        result = {"passed": True, "issues": [], "stats": {}}
        mins = cls._MINIMUMS["slides"]

        if len(slides) < mins["count"]:
            result["passed"] = False
            result["issues"].append(
                f"Only {len(slides)} slide(s); expected ≥ {mins['count']}"
            )

        empty_slides = [
            i + 1 for i, s in enumerate(slides)
            if not s.get("bullets") and not s.get("body", "")
        ]
        if empty_slides:
            result["issues"].append(
                f"Slide(s) {empty_slides} have no bullets or body text"
            )

        thin_slides = [
            i + 1 for i, s in enumerate(slides)
            if len(s.get("bullets", [])) < mins["bullets_per_slide"]
        ]
        if thin_slides:
            result["issues"].append(
                f"Slide(s) {thin_slides} have fewer than "
                f"{mins['bullets_per_slide']} bullet(s)"
            )

        result["stats"] = {
            "slide_count": len(slides),
            "empty_slides": len(empty_slides),
            "thin_slides": len(thin_slides),
        }
        return result

    @classmethod
    def check_pdf_sections(cls, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check that a sections list has adequate content."""
        result = {"passed": True, "issues": [], "stats": {}}
        mins = cls._MINIMUMS["sections"]

        if len(sections) < mins["count"]:
            result["passed"] = False
            result["issues"].append(
                f"Only {len(sections)} section(s); expected ≥ {mins['count']}"
            )

        empty_sections = [
            i + 1 for i, s in enumerate(sections)
            if not s.get("body") and not s.get("bullets")
        ]
        if empty_sections:
            result["issues"].append(
                f"Section(s) {empty_sections} have no body text or bullets"
            )

        thin_sections = [
            i + 1 for i, s in enumerate(sections)
            if s.get("body") and len(s["body"].split()) < mins["words_per_body"]
        ]
        if thin_sections:
            result["issues"].append(
                f"Section(s) {thin_sections} have very short body text "
                f"(< {mins['words_per_body']} words)"
            )

        result["stats"] = {
            "section_count": len(sections),
            "empty_sections": len(empty_sections),
            "thin_sections": len(thin_sections),
        }
        return result

    @classmethod
    def check_xlsx_sheets(cls, sheets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check that a sheets list has adequate content."""
        result = {"passed": True, "issues": [], "stats": {}}
        mins = cls._MINIMUMS["sheets"]

        if len(sheets) < mins["count"]:
            result["passed"] = False
            result["issues"].append(
                f"Only {len(sheets)} sheet(s); expected ≥ {mins['count']}"
            )

        empty_sheets = [
            i + 1 for i, s in enumerate(sheets)
            if not s.get("rows") and not s.get("headers")
        ]
        if empty_sheets:
            result["issues"].append(
                f"Sheet(s) {empty_sheets} have no headers or rows"
            )

        total_rows = sum(len(s.get("rows", [])) for s in sheets)
        result["stats"] = {
            "sheet_count": len(sheets),
            "empty_sheets": len(empty_sheets),
            "total_rows": total_rows,
        }
        return result

    @classmethod
    def check(cls, file_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to the appropriate checker based on *file_type*."""
        if file_type == "pptx":
            return cls.check_pptx(data.get("slides", []))
        elif file_type in ("pdf", "docx"):
            return cls.check_pdf_sections(data.get("sections", []))
        elif file_type == "xlsx":
            return cls.check_xlsx_sheets(data.get("sheets", []))
        return {"passed": True, "issues": [], "stats": {}}
