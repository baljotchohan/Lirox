"""
Lirox v2.0 — Network Diagnostics & Security Audit Logger

Provides:
- Human-readable network error diagnosis
- Quick online/offline check
- Security audit logging for browser operations
"""

import socket
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger("lirox.network.diagnostics")


class NetworkDiagnostics:
    """
    Diagnose network errors and provide actionable feedback.

    Usage:
        diag = NetworkDiagnostics()
        if not diag.is_online():
            print("No internet connection")
        message = diag.diagnose_error(some_exception)
    """

    @staticmethod
    def is_online(timeout: float = 3.0) -> bool:
        """Quick connectivity check via DNS (Google DNS 8.8.8.8)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(("8.8.8.8", 53))
            sock.close()
            return result == 0
        except Exception:
            return False

    @staticmethod
    def diagnose_error(error: Exception) -> str:
        """
        Convert a network exception into a human-readable diagnostic message.

        Args:
            error: The exception to diagnose

        Returns:
            A helpful error message with suggested actions
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Connection refused
        if "connection refused" in error_str or "errno 111" in error_str:
            return (
                "Connection refused — the target server is not accepting connections. "
                "This may mean the service is down or the port is blocked."
            )

        # DNS resolution failure
        if "name resolution" in error_str or "nodename" in error_str or "getaddrinfo" in error_str:
            return (
                "DNS resolution failed — the domain could not be resolved. "
                "Check if the URL is correct and your internet connection is active."
            )

        # Timeout
        if "timeout" in error_str or "timed out" in error_str:
            return (
                "Connection timed out — the server did not respond within the allotted time. "
                "The server may be overloaded or the network is slow."
            )

        # SSL errors
        if "ssl" in error_str or "certificate" in error_str:
            return (
                "SSL/TLS error — the secure connection could not be established. "
                "The server's certificate may be expired or invalid."
            )

        # Too many redirects
        if "redirect" in error_str:
            return (
                "Too many redirects — the URL creates an infinite redirect loop. "
                "This typically indicates a server misconfiguration."
            )

        # Rate limiting
        if "429" in error_str or "rate limit" in error_str:
            return (
                "Rate limited (HTTP 429) — too many requests were sent too quickly. "
                "Wait a moment before trying again."
            )

        # Generic
        return f"Network error ({error_type}): {str(error)[:200]}"


class AuditLogger:
    """
    Security audit logger for browser operations.

    Logs security-relevant events (URL access, JS execution,
    validation failures, rate limit hits) for compliance and debugging.

    Events are written to the standard logging system at INFO/WARNING level.
    """

    def __init__(self, name: str = "lirox.security.audit"):
        self._logger = logging.getLogger(name)

    def log_url_access(self, url: str, allowed: bool, reason: str = "ok") -> None:
        """Log a URL access attempt."""
        status = "ALLOWED" if allowed else "BLOCKED"
        self._logger.info(f"[URL_ACCESS] {status} | url={url} | reason={reason}")

    def log_js_execution(self, script_preview: str, allowed: bool, reason: str = "ok") -> None:
        """Log a JavaScript execution attempt."""
        status = "ALLOWED" if allowed else "BLOCKED"
        preview = script_preview[:100].replace("\n", " ")
        self._logger.info(f"[JS_EXEC] {status} | script={preview}... | reason={reason}")

    def log_rate_limit(self, domain: str, tokens_remaining: int = 0) -> None:
        """Log a rate limit event."""
        self._logger.warning(
            f"[RATE_LIMIT] domain={domain} | tokens_remaining={tokens_remaining}"
        )

    def log_security_violation(self, violation_type: str, details: str) -> None:
        """Log a security policy violation."""
        self._logger.warning(
            f"[SECURITY_VIOLATION] type={violation_type} | details={details}"
        )

    def log_session_event(self, session_id: str, event: str, details: str = "") -> None:
        """Log a browser session lifecycle event."""
        self._logger.info(
            f"[SESSION] id={session_id} | event={event}"
            + (f" | details={details}" if details else "")
        )
