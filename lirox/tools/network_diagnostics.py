"""
Lirox v2.0 — Network Diagnostics

Provides human-readable diagnosis of common network errors.
"""

from __future__ import annotations


class NetworkDiagnostics:
    """Static utility for diagnosing network errors."""

    @staticmethod
    def diagnose_error(error: Exception) -> str:
        """
        Return a human-readable diagnosis for a network exception.

        Args:
            error: Any network-related exception.

        Returns:
            A descriptive string explaining the likely cause.
        """
        msg = str(error).lower()

        if "connection refused" in msg:
            return (
                "Connection refused: The server actively rejected the connection. "
                "The service may be down, the port may be closed, or a firewall "
                "is blocking the request."
            )
        if "timed out" in msg or "timeout" in msg:
            return (
                "Connection timed out: The server did not respond within the "
                "expected time. Check network connectivity or try again later."
            )
        if "name or service not known" in msg or "nodename nor servname" in msg:
            return (
                "DNS resolution failed: The hostname could not be resolved. "
                "Check the URL or your DNS configuration."
            )
        if "ssl" in msg or "certificate" in msg:
            return (
                "SSL/TLS error: Certificate validation failed or the connection "
                "could not be encrypted. The certificate may be expired or invalid."
            )
        if "too many redirects" in msg:
            return (
                "Too many redirects: The server is redirecting in a loop. "
                "Check the URL for configuration issues."
            )

        return f"Network error: {error}"
