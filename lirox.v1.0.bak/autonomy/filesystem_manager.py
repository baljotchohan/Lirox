"""Lirox Autonomy — Intelligent Filesystem Manager

Auto-discovers project structure, manages file permissions, creates files
at correct paths, and maintains backups before modifications.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class FilesystemManager:
    """Safe, project-aware file-system operations with automatic backup."""

    # ------------------------------------------------------------------
    # Project discovery
    # ------------------------------------------------------------------

    def discover_structure(self, root: str) -> Dict[str, List[str]]:
        """Walk *root* and return a map of ``rel_dir → [filenames]``.

        Hidden directories and ``__pycache__`` / ``.git`` are skipped.
        """
        structure: Dict[str, List[str]] = {}
        root_path = Path(root).resolve()

        for dirpath, dirnames, filenames in os.walk(root_path):
            # Prune hidden / irrelevant directories in-place
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in ("__pycache__", "node_modules")
            ]
            rel = str(Path(dirpath).relative_to(root_path))
            structure[rel] = sorted(filenames)

        return structure

    def find_module_file(self, module_name: str, root: str) -> Optional[str]:
        """Return the absolute path to *module_name*.py under *root*, or None."""
        for path in Path(root).rglob(f"{module_name}.py"):
            if "__pycache__" not in str(path):
                return str(path)
        return None

    def get_python_files(self, root: str) -> List[str]:
        """Return sorted list of all .py file paths under *root*."""
        return sorted(
            str(p) for p in Path(root).rglob("*.py")
            if "__pycache__" not in str(p) and ".git" not in str(p)
        )

    # ------------------------------------------------------------------
    # Safe read / write
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> Tuple[bool, str]:
        """Read a file safely.  Returns ``(success, content_or_error)``."""
        try:
            return True, Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return False, f"Read error: {exc}"

    def write_file(
        self, path: str, content: str, backup: bool = True
    ) -> Tuple[bool, str]:
        """Write *content* to *path*, optionally creating a backup first.

        Returns ``(success, message)``.
        """
        target = Path(path).expanduser().resolve()

        # Ensure parent directory exists
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return False, f"Cannot create directory {target.parent}: {exc}"

        # Create backup if file already exists
        if backup and target.exists():
            backup_path = target.with_suffix(target.suffix + f".bak.{int(time.time())}")
            try:
                shutil.copy2(str(target), str(backup_path))
            except OSError:
                pass  # backup failure is non-fatal

        try:
            target.write_text(content, encoding="utf-8")
            return True, f"Written {len(content)} chars to {target}"
        except OSError as exc:
            return False, f"Write error: {exc}"

    def append_to_file(self, path: str, content: str) -> Tuple[bool, str]:
        """Append *content* to *path*, creating it if necessary."""
        target = Path(path).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(content)
            return True, f"Appended {len(content)} chars to {target}"
        except OSError as exc:
            return False, f"Append error: {exc}"

    def delete_file(self, path: str, backup: bool = True) -> Tuple[bool, str]:
        """Delete *path*, optionally backing it up first."""
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return False, f"File not found: {target}"

        if backup:
            backup_path = target.with_suffix(target.suffix + f".bak.{int(time.time())}")
            try:
                shutil.copy2(str(target), str(backup_path))
            except OSError:
                pass

        try:
            target.unlink()
            return True, f"Deleted {target}"
        except OSError as exc:
            return False, f"Delete error: {exc}"

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def resolve_project_path(self, relative: str, project_root: str) -> str:
        """Resolve *relative* against *project_root*, handling ``~`` expansion."""
        return str((Path(project_root) / relative).expanduser().resolve())

    def ensure_dir(self, path: str) -> Tuple[bool, str]:
        """Create *path* as a directory (and parents) if it doesn't exist."""
        try:
            Path(path).expanduser().resolve().mkdir(parents=True, exist_ok=True)
            return True, f"Directory ready: {path}"
        except OSError as exc:
            return False, f"Cannot create directory: {exc}"
