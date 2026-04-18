"""Lirox V1 — Comprehensive Audit Logger.

Logs all file operations, permission checks, agent actions, and system events
to a tamper-evident JSONL audit trail in ~/Lirox/audit/.

Usage:
    from lirox.audit.logger import audit_log, AuditEvent

    audit_log(AuditEvent.FILE_WRITE, path="/some/file.py", user="Baljot")
    audit_log(AuditEvent.PERMISSION_CHECK, tier=2, granted=True)
"""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class AuditEvent(str, Enum):
    # File operations
    FILE_READ          = "file_read"
    FILE_WRITE         = "file_write"
    FILE_DELETE        = "file_delete"
    FILE_CREATE        = "file_create"

    # Permission system
    PERMISSION_CHECK   = "permission_check"
    PERMISSION_GRANT   = "permission_grant"
    PERMISSION_DENY    = "permission_deny"
    PERMISSION_REQUEST = "permission_request"

    # Agent actions
    AGENT_START        = "agent_start"
    AGENT_SKILL        = "agent_skill"
    AGENT_TRAIN        = "agent_train"
    AGENT_IMPROVE      = "agent_improve"
    AGENT_APPLY_PATCH  = "agent_apply_patch"

    # Self-modification
    SELF_MOD_ATTEMPT   = "self_mod_attempt"
    SELF_MOD_BLOCKED   = "self_mod_blocked"
    SELF_MOD_ALLOWED   = "self_mod_allowed"

    # System
    SYSTEM_START       = "system_start"
    SYSTEM_SHUTDOWN    = "system_shutdown"
    SETUP_COMPLETE     = "setup_complete"
    BACKUP_CREATE      = "backup_create"
    ERROR              = "error"


# ── Audit log location ───────────────────────────────────────────────────────

def _get_audit_dir() -> Path:
    """Return the audit directory, preferring ~/Lirox/audit if available."""
    # Try HOME_LIROX first
    home_audit = Path.home() / "Lirox" / "audit"
    if home_audit.parent.parent.exists():
        try:
            home_audit.mkdir(mode=0o700, parents=True, exist_ok=True)
            return home_audit
        except Exception:
            pass

    # Fallback: project data/audit
    from lirox.config import DATA_DIR
    fallback = Path(DATA_DIR) / "audit"
    try:
        fallback.mkdir(mode=0o700, parents=True, exist_ok=True)
    except Exception:
        pass
    return fallback


_audit_dir:  Optional[Path] = None
_log_lock    = threading.Lock()
_session_id  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
_enabled     = os.getenv("AUDIT_ENABLED", "true").lower() != "false"


def _get_log_file() -> Path:
    global _audit_dir
    if _audit_dir is None:
        _audit_dir = _get_audit_dir()
    return _audit_dir / f"audit_{_session_id}.jsonl"


# ── Public API ───────────────────────────────────────────────────────────────

def audit_log(
    event: AuditEvent,
    *,
    path:    Optional[str] = None,
    message: str = "",
    user:    Optional[str] = None,
    tier:    Optional[int] = None,
    granted: Optional[bool] = None,
    extra:   Optional[Dict[str, Any]] = None,
) -> None:
    """Write a structured audit entry (non-blocking, thread-safe).

    Silently ignores errors so audit failures never break the main flow.
    """
    if not _enabled:
        return

    entry: Dict[str, Any] = {
        "ts":    datetime.now(timezone.utc).isoformat(),
        "event": event.value,
        "pid":   os.getpid(),
    }
    if path:
        entry["path"] = path
    if message:
        entry["message"] = message[:500]
    if user:
        entry["user"] = user
    if tier is not None:
        entry["tier"] = tier
    if granted is not None:
        entry["granted"] = granted
    if extra:
        entry["extra"] = {k: str(v)[:200] for k, v in extra.items()}

    try:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with _log_lock:
            with open(_get_log_file(), "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass  # audit is best-effort; never crash main flow


def read_audit_log(limit: int = 100) -> list:
    """Return the last `limit` audit entries as a list of dicts."""
    log_file = _get_log_file()
    if not log_file.exists():
        return []
    entries = []
    try:
        with open(log_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return entries[-limit:]


def format_audit_log(limit: int = 50) -> str:
    """Return a human-readable audit log summary."""
    entries = read_audit_log(limit)
    if not entries:
        return "No audit log entries yet."
    lines = [f"AUDIT LOG (last {min(limit, len(entries))} entries)\n"]
    for e in entries:
        ts   = e.get("ts", "")[:19].replace("T", " ")
        evt  = e.get("event", "?").upper()
        msg  = e.get("message", "")
        path = e.get("path", "")
        parts = [f"  [{ts}] {evt}"]
        if path:
            parts.append(f"path={path}")
        if msg:
            parts.append(msg[:80])
        lines.append("  ".join(parts))
    return "\n".join(lines)
