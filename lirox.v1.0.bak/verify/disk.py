"""Disk-level verification helpers.

These are the last line of defense against hallucinated success.
After every write/delete, one of these is called to confirm the
state of the filesystem matches what the tool claims.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Tuple


def verify_file_exists(path: str) -> Tuple[bool, str]:
    """Returns (exists, reason). Resolves symlinks."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return False, f"Path does not exist on disk: {p}"
        if not p.is_file():
            return False, f"Path exists but is not a regular file: {p}"
        return True, f"File verified at {p} (size={p.stat().st_size} bytes)"
    except OSError as e:
        return False, f"Verification OS error: {e}"


def verify_file_content_matches(path: str, expected_content: str,
                                 sample_size: int = 256) -> Tuple[bool, str]:
    """Verifies the written content is actually on disk.

    For large files, compares a hash of the first `sample_size` bytes
    plus the last `sample_size` bytes — fast and reliable.
    """
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return False, "File missing during content check"

        actual = p.read_text(encoding="utf-8", errors="replace")
        if len(expected_content) <= sample_size * 2:
            if actual == expected_content:
                return True, "Content byte-exact match"
            return False, (
                f"Content mismatch: expected {len(expected_content)} chars, "
                f"found {len(actual)} chars"
            )

        # Large file: hash head+tail
        def _h(s: str) -> str:
            return hashlib.md5(s.encode("utf-8", errors="replace")).hexdigest()

        if (_h(actual[:sample_size]) == _h(expected_content[:sample_size])
                and _h(actual[-sample_size:]) == _h(expected_content[-sample_size:])
                and len(actual) == len(expected_content)):
            return True, "Content hash-verified (head+tail+size)"
        return False, (
            f"Large-file content mismatch: "
            f"expected {len(expected_content)} chars, found {len(actual)} chars"
        )
    except OSError as e:
        return False, f"Content verification OS error: {e}"


def verify_dir_exists(path: str) -> Tuple[bool, str]:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return False, f"Directory does not exist: {p}"
        if not p.is_dir():
            return False, f"Path exists but is not a directory: {p}"
        return True, f"Directory verified at {p}"
    except OSError as e:
        return False, f"Verification OS error: {e}"


def verify_file_deleted(path: str) -> Tuple[bool, str]:
    try:
        p = Path(path).expanduser()
        if p.exists():
            return False, f"Deletion failed — path still exists: {p}"
        return True, f"Deletion verified (path absent): {p}"
    except OSError as e:
        return False, f"Verification OS error: {e}"
