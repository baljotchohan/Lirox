"""Lirox v1.1 — Core Error Hierarchy

Root-cause fix: all Lirox errors now have a clear hierarchy, structured
metadata (severity, retryable flag, context dict), and consistent string
representations.  Callers can catch LiroxError for any Lirox-specific
failure, or catch a subclass for finer control.

Backwards-compatible shim: lirox.utils.errors re-exports from here so
existing import sites continue to work unchanged.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LiroxError(Exception):
    """Base class for every Lirox exception.

    Attributes
    ----------
    message : str
        Human-readable description.
    severity : Severity
        Indicates urgency level for logging/alerting.
    retryable : bool
        True when the operation *might* succeed on a subsequent attempt.
    context : dict
        Arbitrary key/value metadata attached by the raising site.
    """

    def __init__(
        self,
        message: str,
        severity: Severity = Severity.MEDIUM,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.retryable = retryable
        self.context: Dict[str, Any] = context or {}

    def __str__(self) -> str:
        parts = [f"[{self.severity.value.upper()}] {self.message}"]
        if self.context:
            parts.append(f"context={self.context!r}")
        return " | ".join(parts)


class ConfigurationError(LiroxError):
    """Raised when configuration is invalid, missing, or inconsistent."""

    def __init__(self, message: str, key: str = "", expected: str = "") -> None:
        ctx: Dict[str, Any] = {}
        if key:
            ctx["key"] = key
        if expected:
            ctx["expected"] = expected
        super().__init__(message, severity=Severity.HIGH, retryable=False, context=ctx)
        self.key = key
        self.expected = expected


class ProviderError(LiroxError):
    """Raised when an LLM provider call fails."""

    def __init__(
        self,
        provider: str,
        message: str,
        retryable: bool = True,
        status_code: Optional[int] = None,
    ) -> None:
        ctx: Dict[str, Any] = {"provider": provider}
        if status_code is not None:
            ctx["status_code"] = status_code
        super().__init__(
            f"[{provider}] {message}",
            severity=Severity.HIGH,
            retryable=retryable,
            context=ctx,
        )
        self.provider = provider
        self.status_code = status_code


class ToolError(LiroxError):
    """Raised when a tool (terminal, file, search) fails to execute."""

    def __init__(
        self,
        tool: str,
        message: str,
        retryable: bool = False,
        exit_code: Optional[int] = None,
    ) -> None:
        ctx: Dict[str, Any] = {"tool": tool}
        if exit_code is not None:
            ctx["exit_code"] = exit_code
        super().__init__(
            f"[{tool}] {message}",
            severity=Severity.MEDIUM,
            retryable=retryable,
            context=ctx,
        )
        self.tool = tool
        self.exit_code = exit_code


class SecurityError(LiroxError):
    """Raised when a security check fails (blocked path, injection, etc.)."""

    def __init__(self, message: str, path: str = "", reason: str = "") -> None:
        ctx: Dict[str, Any] = {}
        if path:
            ctx["path"] = path
        if reason:
            ctx["reason"] = reason
        super().__init__(message, severity=Severity.CRITICAL, retryable=False, context=ctx)


class DataError(LiroxError):
    """Raised when data parsing, validation, or serialization fails."""

    def __init__(
        self,
        message: str,
        data_type: str = "",
        retryable: bool = False,
    ) -> None:
        ctx: Dict[str, Any] = {}
        if data_type:
            ctx["data_type"] = data_type
        super().__init__(message, severity=Severity.MEDIUM, retryable=retryable, context=ctx)
        self.data_type = data_type


class LiroxMemoryError(LiroxError):
    """Raised when memory operations fail."""

    def __init__(self, message: str, agent: str = "", retryable: bool = False) -> None:
        ctx: Dict[str, Any] = {}
        if agent:
            ctx["agent"] = agent
        super().__init__(message, severity=Severity.MEDIUM, retryable=retryable, context=ctx)


class TransactionError(LiroxError):
    """Raised when an atomic transaction cannot be committed or rolled back."""

    def __init__(self, message: str, path: str = "") -> None:
        ctx: Dict[str, Any] = {}
        if path:
            ctx["path"] = path
        super().__init__(message, severity=Severity.HIGH, retryable=False, context=ctx)


# ---------------------------------------------------------------------------
# Retry helpers — kept here so callers only need one import
# ---------------------------------------------------------------------------

_RETRYABLE_SUBSTRINGS = (
    "timeout", "timed out", "rate limit", "rate_limit",
    "429", "503", "502", "connection", "temporary",
    "temporarily", "try again", "server error",
)


def is_retryable(exc: BaseException) -> bool:
    """Return True when *exc* looks like a transient, retriable failure."""
    if isinstance(exc, LiroxError):
        return exc.retryable
    msg = str(exc).lower()
    return any(sub in msg for sub in _RETRYABLE_SUBSTRINGS)
