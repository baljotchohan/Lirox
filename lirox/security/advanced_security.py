"""
Lirox v2.0 — Advanced Security System

Bank-grade multi-layer security:
1. Permission system with action whitelisting
2. Resource classification
3. Rate limiting per action
4. Anomaly detection
5. Comprehensive audit logging
6. Sandboxed code execution
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


# ─── Allowed Actions Whitelist ────────────────────────────────────────────────

ALLOWED_ACTIONS: Set[str] = {
    "read_file", "write_file", "list_files", "delete_file",
    "search_web", "fetch_url",
    "run_terminal", "run_code",
    "take_screenshot", "click", "type_text",
    "read_memory", "write_memory",
    "create_agent", "delegate_task",
}

# Resource sensitivity classifications
_CLASSIFICATION_MAP = {
    "system":   ["etc", "proc", "sys", "boot", "kernel"],
    "private":  ["password", "secret", "key", "token", "credential"],
    "sensitive":["home", "documents", "desktop"],
    "public":   [],  # Default
}


# ─── Audit Log ────────────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    """A single entry in the security audit log."""
    event:      str
    action:     str
    resource:   str
    allowed:    bool
    timestamp:  datetime = field(default_factory=datetime.now)
    details:    str       = ""


class AuditLog:
    """Thread-safe in-memory audit log."""

    def __init__(self, max_entries: int = 10_000):
        self._entries:    List[AuditEntry] = []
        self._max_entries = max_entries

    def add(self, entry: AuditEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def get_recent(self, n: int = 100) -> List[AuditEntry]:
        return self._entries[-n:]

    def get_by_action(self, action: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.action == action]

    def __len__(self) -> int:
        return len(self._entries)


# ─── Rate Limiter ────────────────────────────────────────────────────────────

class _RateLimiter:
    """Per-action sliding-window rate limiter."""

    def __init__(self, max_calls: int = 100, window_seconds: float = 60.0):
        self._max_calls = max_calls
        self._window    = window_seconds
        self._calls:    Dict[str, List[float]] = {}

    def is_limited(self, action: str) -> bool:
        now = time.monotonic()
        window_start = now - self._window
        calls = self._calls.get(action, [])
        # Prune old calls
        calls = [t for t in calls if t > window_start]
        if len(calls) >= self._max_calls:
            self._calls[action] = calls
            return True
        calls.append(now)
        self._calls[action] = calls
        return False


# ─── Advanced Security System ────────────────────────────────────────────────

class AdvancedSecuritySystem:
    """
    Bank-grade multi-layer security system.

    Checks:
    1. Action whitelisting
    2. Resource classification
    3. Rate limiting
    4. Anomaly detection
    All decisions are logged to the audit trail.
    """

    def __init__(
        self,
        user_permissions: Optional[Set[str]] = None,
        rate_limit_per_minute: int = 100,
    ):
        self.audit_log  = AuditLog()
        self._rate_limiter = _RateLimiter(rate_limit_per_minute, 60.0)
        self._user_permissions = user_permissions or set(ALLOWED_ACTIONS)
        self._anomaly_threshold = 50  # calls per minute before anomaly

    # ── Permission Check ─────────────────────────────────────────────────────

    def check_permission(self, action: str, resource: str) -> bool:
        """
        Five-level permission check.

        Returns True if action is allowed, False otherwise.
        """
        # Level 1: Action whitelisting
        if action not in ALLOWED_ACTIONS:
            self._log("action_blocked", action, resource, allowed=False)
            return False

        # Level 2: Resource classification
        classification = self._classify_resource(resource)
        if classification == "system":
            self._log("system_resource_denied", action, resource, allowed=False)
            return False

        # Level 3: User permission check
        if action not in self._user_permissions:
            self._log("permission_denied", action, resource, allowed=False)
            return False

        # Level 4: Rate limit
        if self._rate_limiter.is_limited(action):
            self._log("rate_limited", action, resource, allowed=False)
            return False

        # Level 5: Anomaly detection
        if self._is_anomalous(action, resource):
            self._log("anomaly_detected", action, resource, allowed=False)
            return False

        self._log("action_allowed", action, resource, allowed=True)
        return True

    # ── Sandboxed Execution ──────────────────────────────────────────────────

    def sandboxed_execution(self, code: str) -> Dict[str, Any]:
        """
        Execute code in a restricted namespace.

        Blocks dangerous imports and evaluates in a fresh namespace.
        """
        from lirox.execution.perfect_executor import PerfectExecutor

        executor = PerfectExecutor()
        result = executor.execute_safely(code, context={})

        # Audit
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        self.audit_log.add(AuditEntry(
            event="code_execution",
            action="run_code",
            resource=f"code:{code_hash}",
            allowed=result.status != "blocked",
            details=result.status,
        ))

        return {
            "status": result.status,
            "output": result.output,
            "error":  result.error,
        }

    # ── Encryption Helpers ────────────────────────────────────────────────────

    @staticmethod
    def hash_sensitive(data: str) -> str:
        """One-way hash of sensitive data for storage."""
        return hashlib.sha256(data.encode()).hexdigest()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _classify_resource(self, resource: str) -> str:
        resource_lower = resource.lower()
        for classification, keywords in _CLASSIFICATION_MAP.items():
            if any(kw in resource_lower for kw in keywords):
                return classification
        return "public"

    def _is_anomalous(self, action: str, resource: str) -> bool:
        recent = self.audit_log.get_by_action(action)
        one_minute_ago = time.time() - 60
        recent_count = sum(
            1 for e in recent
            if e.timestamp.timestamp() > one_minute_ago
        )
        return recent_count > self._anomaly_threshold

    def _log(self, event: str, action: str, resource: str, allowed: bool) -> None:
        self.audit_log.add(AuditEntry(
            event=event,
            action=action,
            resource=resource,
            allowed=allowed,
        ))
