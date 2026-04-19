"""Lirox v1.1 — Atomic File Transaction Framework

Root-cause fix (C-04): replaces direct open(path, 'w') calls with an
atomic write-then-rename pattern so that a crash or exception mid-write
never leaves a partially-written (corrupt) file on disk.

Usage — simple one-shot write
------------------------------
    from lirox.core.transaction import atomic_write

    atomic_write("/data/soul.json", json.dumps(data, indent=2))

Usage — multi-step transaction
--------------------------------
    from lirox.core.transaction import AtomicTransaction

    with AtomicTransaction() as tx:
        tx.write("/data/a.json", content_a)
        tx.write("/data/b.json", content_b)
    # Both files are renamed atomically on __exit__.
    # If an exception is raised inside the block, all temp files are removed.

Thread safety
-------------
Each AtomicTransaction instance uses its own set of temp files.  It is
NOT safe to share a single AtomicTransaction across threads — create one
per thread/task.
"""
from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Simple helper — single atomic write
# ---------------------------------------------------------------------------

def atomic_write(
    path: str,
    content: str,
    encoding: str = "utf-8",
    mode: int = 0o600,
) -> None:
    """Write *content* to *path* atomically.

    The data is first written to a sibling temp file in the same directory
    (guaranteeing the rename is on the same filesystem), then renamed into
    place.  If any step fails the temp file is cleaned up and the original
    *path* is left untouched.

    Parameters
    ----------
    path : str
        Destination file path.
    content : str
        Text content to write.
    encoding : str
        Text encoding (default: 'utf-8').
    mode : int
        Unix permission bits for the final file (default: 0o600).

    Raises
    ------
    OSError
        If the write or rename fails (caller may choose to handle or propagate).
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(dest.parent),
        prefix=f".{dest.name}.tmp.",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, str(dest))  # atomic on POSIX; best-effort on Windows
    except Exception:
        # Clean up the temp file if anything went wrong.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_bytes(
    path: str,
    data: bytes,
    mode: int = 0o600,
) -> None:
    """Binary variant of :func:`atomic_write`."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(dest.parent),
        prefix=f".{dest.name}.tmp.",
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, str(dest))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Multi-step transaction
# ---------------------------------------------------------------------------

class AtomicTransaction:
    """Context manager that batches multiple file writes into an atomic set.

    Writes are staged to temp files; on successful exit they are all renamed
    into place.  On exception, all staged temp files are removed and the
    original files remain untouched.

    Example
    -------
        with AtomicTransaction() as tx:
            tx.write("a.json", json_a)
            tx.write("b.json", json_b)
        # Committed — both files now exist on disk.
    """

    def __init__(self, encoding: str = "utf-8", file_mode: int = 0o600) -> None:
        self._encoding = encoding
        self._file_mode = file_mode
        # List of (tmp_path, dest_path) pairs staged for rename.
        self._staged: List[Tuple[str, str]] = []
        self._lock = threading.Lock()

    # ── Context manager protocol ─────────────────────────────────────────────

    def __enter__(self) -> "AtomicTransaction":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self._commit()
        else:
            self._rollback()
        return False  # never suppress exceptions

    # ── Public API ───────────────────────────────────────────────────────────

    def write(self, path: str, content: str) -> None:
        """Stage a text write for *path* with *content*.

        The actual rename happens on successful ``__exit__``.
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(dest.parent),
            prefix=f".{dest.name}.tmp.",
        )
        try:
            with os.fdopen(fd, "w", encoding=self._encoding) as fh:
                fh.write(content)
            os.chmod(tmp_path, self._file_mode)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        with self._lock:
            self._staged.append((tmp_path, str(dest)))

    def write_bytes(self, path: str, data: bytes) -> None:
        """Stage a binary write for *path*."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(dest.parent),
            prefix=f".{dest.name}.tmp.",
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.chmod(tmp_path, self._file_mode)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        with self._lock:
            self._staged.append((tmp_path, str(dest)))

    # ── Internal ─────────────────────────────────────────────────────────────

    def _commit(self) -> None:
        """Rename all staged temp files to their destinations."""
        with self._lock:
            staged = list(self._staged)
        for tmp_path, dest_path in staged:
            try:
                os.replace(tmp_path, dest_path)
            except OSError as exc:
                from lirox.core.errors import TransactionError
                raise TransactionError(
                    f"Commit failed renaming {tmp_path!r} → {dest_path!r}: {exc}",
                    path=dest_path,
                ) from exc
        with self._lock:
            self._staged.clear()

    def _rollback(self) -> None:
        """Remove all staged temp files, leaving originals untouched."""
        with self._lock:
            staged = list(self._staged)
            self._staged.clear()
        for tmp_path, _ in staged:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
