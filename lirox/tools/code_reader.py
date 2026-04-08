"""
Lirox v1.0.0 — Code Reader Tool

Safe code file reader that reads source files from the filesystem while
respecting the SAFE_DIRS sandbox. Supports multiple languages and returns
file contents together with metadata (language, line count, file size).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from lirox.config import SAFE_DIRS


# Mapping of file extensions to language names
_EXTENSION_MAP: dict[str, str] = {
    ".py":    "python",
    ".js":    "javascript",
    ".ts":    "typescript",
    ".java":  "java",
    ".go":    "go",
    ".rs":    "rust",
    ".cpp":   "cpp",
    ".c":     "c",
    ".cs":    "csharp",
    ".rb":    "ruby",
    ".php":   "php",
    ".swift": "swift",
    ".kt":    "kotlin",
}

SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(_EXTENSION_MAP.keys())


class CodeReader:
    """
    Safe reader for source-code files.

    All paths are validated against ``SAFE_DIRS`` before any file is
    opened, preventing directory-traversal and out-of-sandbox access.
    """

    def __init__(self) -> None:
        self._safe_dirs: list[Path] = [Path(d).resolve() for d in SAFE_DIRS]

    # ── Path safety ──────────────────────────────────────────────────────────

    def _is_safe_path(self, file_path: str) -> tuple[bool, str]:
        """
        Check whether *file_path* is inside one of the allowed directories.

        Args:
            file_path: Absolute or relative path to check.

        Returns:
            ``(True, "ok")`` if the path is safe, otherwise
            ``(False, reason)`` explaining why it was rejected.
        """
        try:
            target = Path(file_path).expanduser().resolve()
            for safe_dir in self._safe_dirs:
                if target.is_relative_to(safe_dir):
                    return True, "ok"
            return False, f"Path outside safe dirs: {target}"
        except (ValueError, OSError) as exc:
            return False, f"Path resolution error: {exc}"

    # ── Language detection ───────────────────────────────────────────────────

    def detect_language(self, path: str) -> str:
        """
        Detect the programming language from the file extension.

        Args:
            path: File path (only the extension is examined).

        Returns:
            A lowercase language name (e.g. ``"python"``), or
            ``"unknown"`` when the extension is not recognised.
        """
        ext = Path(path).suffix.lower()
        return _EXTENSION_MAP.get(ext, "unknown")

    # ── Single-file read ─────────────────────────────────────────────────────

    def read_file(self, path: str) -> dict:
        """
        Read a single code file and return its contents with metadata.

        Args:
            path: Absolute or relative path to the source file.

        Returns:
            A dict with keys:

            * ``success`` (bool)
            * ``content`` (str) – file text, empty on failure
            * ``language`` (str)
            * ``line_count`` (int)
            * ``size_bytes`` (int)
            * ``path`` (str) – resolved absolute path
            * ``error`` (str) – non-empty only on failure
        """
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {
                "success": False,
                "content": "",
                "language": "unknown",
                "line_count": 0,
                "size_bytes": 0,
                "path": path,
                "error": f"Access denied: {reason}",
            }

        resolved = str(Path(path).expanduser().resolve())
        language = self.detect_language(resolved)

        try:
            with open(resolved, "r", encoding="utf-8") as fh:
                content = fh.read()
            line_count = content.count("\n") + (1 if content else 0)
            size_bytes = os.path.getsize(resolved)
            return {
                "success": True,
                "content": content,
                "language": language,
                "line_count": line_count,
                "size_bytes": size_bytes,
                "path": resolved,
                "error": "",
            }
        except FileNotFoundError:
            return self._error(path, language, f"File not found: {path}")
        except PermissionError:
            return self._error(path, language, f"Permission denied: {path}")
        except UnicodeDecodeError:
            return self._error(path, language, f"Cannot read binary file: {path}")
        except Exception as exc:
            return self._error(path, language, f"Error reading {path}: {exc}")

    # ── Directory read ───────────────────────────────────────────────────────

    def read_directory(self, path: str, max_files: int = 10) -> dict:
        """
        Read all supported code files in a directory (non-recursive).

        Args:
            path:      Path to the directory.
            max_files: Maximum number of files to read (default 10).

        Returns:
            A dict with keys:

            * ``success`` (bool)
            * ``files`` (list[dict]) – list of :meth:`read_file` results
            * ``total_found`` (int) – number of code files found
            * ``total_read`` (int) – number actually read (≤ max_files)
            * ``path`` (str) – resolved directory path
            * ``error`` (str)
        """
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {
                "success": False,
                "files": [],
                "total_found": 0,
                "total_read": 0,
                "path": path,
                "error": f"Access denied: {reason}",
            }

        resolved = str(Path(path).expanduser().resolve())

        if not os.path.isdir(resolved):
            return {
                "success": False,
                "files": [],
                "total_found": 0,
                "total_read": 0,
                "path": resolved,
                "error": f"Not a directory: {resolved}",
            }

        try:
            all_entries = sorted(os.listdir(resolved))
        except PermissionError as exc:
            return {
                "success": False,
                "files": [],
                "total_found": 0,
                "total_read": 0,
                "path": resolved,
                "error": f"Permission denied: {exc}",
            }

        code_files = [
            e for e in all_entries
            if Path(e).suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        total_found = len(code_files)
        results: list[dict] = []
        for entry in code_files[:max_files]:
            full = os.path.join(resolved, entry)
            results.append(self.read_file(full))

        return {
            "success": True,
            "files": results,
            "total_found": total_found,
            "total_read": len(results),
            "path": resolved,
            "error": "",
        }

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _error(path: str, language: str, message: str) -> dict:
        """Build a uniform failure response."""
        return {
            "success": False,
            "content": "",
            "language": language,
            "line_count": 0,
            "size_bytes": 0,
            "path": path,
            "error": message,
        }
