"""Lirox v1.1 — Structured Logging

Root-cause fix: every module now uses a named child logger from the
'lirox' hierarchy instead of bare print() or silent pass blocks.

Usage
-----
    from lirox.core.logger import get_logger
    _log = get_logger(__name__)
    _log.info("Operation complete")
    _log.warning("Degraded mode: %s", reason)
    _log.error("Failed: %s", exc, exc_info=True)

Initialisation
--------------
Call ``configure_logging()`` once from main() before any other imports.
If never called, the standard Python logging defaults apply (root logger
at WARNING level writing to stderr), which is safe for library use.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'lirox' hierarchy.

    If *name* already starts with 'lirox' it is used as-is; otherwise
    'lirox.' is prepended so all Lirox loggers share the same root and
    can be filtered/configured together.
    """
    if not name.startswith("lirox"):
        name = f"lirox.{name}"
    return logging.getLogger(name)


def configure_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    structured: bool = False,
) -> None:
    """Configure the 'lirox' logger hierarchy.

    Parameters
    ----------
    level : str, optional
        Log level name ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        Defaults to the value of the LIROX_LOG_LEVEL env var, or 'WARNING'.
    log_file : str, optional
        If provided, log records are also written to this file (appended).
    structured : bool
        When True, emit JSON-formatted records (useful for log aggregators).
        When False (default), emit human-readable text.
    """
    level_name = level or os.getenv("LIROX_LOG_LEVEL", "WARNING")
    numeric_level = getattr(logging, level_name.upper(), logging.WARNING)

    root = logging.getLogger("lirox")
    root.setLevel(numeric_level)

    # Avoid adding duplicate handlers if called more than once.
    if root.handlers:
        return

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)

    if structured:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # ── Optional file handler ────────────────────────────────────────────────
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            root.warning("Could not open log file %s: %s", log_file, exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record (no newline inside the object)."""

    def format(self, record: logging.LogRecord) -> str:
        import json as _json
        import traceback as _tb

        payload: dict = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = _tb.format_exception(*record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info
        return _json.dumps(payload, ensure_ascii=False)
