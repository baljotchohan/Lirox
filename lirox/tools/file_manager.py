"""
Lirox v1.0.0 — File Manager

High-level wrapper around the low-level file_tools functions.
Provides a clean class interface with rich feedback messages that
tell the user exactly where files were created or read from.
"""
from __future__ import annotations

import os
from typing import List


class FileManager:
    """Handle all file operations with full path feedback."""

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_file(self, path: str, max_chars: int = 8000) -> str:
        """Read a file and return its contents.

        Args:
            path:      Absolute or relative path to the file.
            max_chars: Maximum number of characters to read.

        Returns:
            File contents with a header showing the resolved path,
            or an error message if the read fails.
        """
        from lirox.tools.file_tools import file_read
        return file_read(path, max_chars=max_chars)

    # ── Write ─────────────────────────────────────────────────────────────────

    def write_file(
        self, path: str, content: str, create_dirs: bool = True
    ) -> str:
        """Write *content* to *path*, optionally creating parent directories.

        Args:
            path:        Destination file path.
            content:     Text content to write.
            create_dirs: When True, missing parent directories are created
                         automatically (default: True).

        Returns:
            A confirmation string with the resolved absolute path, or an
            error message on failure.
        """
        from lirox.tools.file_tools import file_write, _is_safe_path

        ok, info = _is_safe_path(path)
        if not ok:
            return info

        if create_dirs:
            parent = os.path.dirname(info)
            if parent:
                try:
                    os.makedirs(parent, exist_ok=True)
                except OSError as exc:
                    return f"Write error (could not create directory): {exc}"

        result = file_write(path, content)
        return result

    # ── List ──────────────────────────────────────────────────────────────────

    def list_files(self, path: str = ".", pattern: str = "*") -> List[str]:
        """List directory contents matching *pattern*.

        Args:
            path:    Directory to list.
            pattern: Glob pattern to filter entries (default ``"*"``).

        Returns:
            A list of formatted strings describing each entry, or a
            single-element list with an error message on failure.
        """
        from lirox.tools.file_tools import file_list
        result = file_list(path, pattern)
        # Split formatted output into lines for the caller's convenience
        if result.startswith("📁") or result.startswith("No files"):
            return result.splitlines()
        return [result]

    # ── Search ────────────────────────────────────────────────────────────────

    def search_files(self, root: str, query: str) -> List[str]:
        """Search files recursively under *root* for *query*.

        Searches by filename substring first; then searches file
        contents for text files.

        Args:
            root:  Root directory to search from.
            query: Search string (case-insensitive).

        Returns:
            A list of match strings formatted as ``path:line: text``,
            or a single-element list with an error / no-match message.
        """
        from lirox.tools.file_tools import file_search
        result = file_search(root, query)
        return result.splitlines() if result else [f"No matches for '{query}' in {root}"]

    # ── Convenience dispatcher ────────────────────────────────────────────────

    def execute(self, operation: dict) -> str:
        """Execute a file operation described by *operation* dict.

        The dict must contain an ``"op"`` key with one of:
        ``read_file``, ``write_file``, ``list_files``, ``search_files``.

        Additional keys vary by operation:
        - ``read_file``:   ``path``
        - ``write_file``:  ``path``, ``content``
        - ``list_files``:  ``path``, (optional) ``pattern``
        - ``search_files``: ``path``, ``query``

        Returns:
            A human-readable result string.
        """
        op      = operation.get("op", "")
        path    = operation.get("path", ".")
        content = operation.get("content", "")
        pattern = operation.get("pattern", "*")
        query   = operation.get("query", "")

        if op == "read_file":
            return self.read_file(path)
        if op == "write_file":
            return self.write_file(path, content)
        if op == "list_files":
            return "\n".join(self.list_files(path, pattern))
        if op == "search_files":
            return "\n".join(self.search_files(path, query))
        return f"Unknown file operation: '{op}'"
