"""
Lirox v1.1 — Browser Security

Multi-layer URL and request validation:
- SSRF protection (private IPs, cloud metadata endpoints)
- Dangerous port blocking
- CRLF/null-byte header injection prevention
- Prototype pollution detection
- Per-domain token-bucket rate limiting
"""

from __future__ import annotations

import ipaddress
import re
import time
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse


# ─── Dangerous Ports ─────────────────────────────────────────────────────────

_BLOCKED_PORTS = {
    21,   # FTP
    22,   # SSH
    23,   # Telnet
    25,   # SMTP
    110,  # POP3
    143,  # IMAP
    3306, # MySQL
    5432, # PostgreSQL
    6379, # Redis
    27017,# MongoDB
}

# ─── Private/Reserved Networks ───────────────────────────────────────────────

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local & cloud metadata (AWS/Azure/GCP)
    ipaddress.ip_network("100.64.0.0/10"),    # Shared address space
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# ─── JavaScript Dangerous Patterns ───────────────────────────────────────────

_JS_DANGEROUS_PATTERNS = [
    r"__proto__",
    r"constructor\s*\[",
    r"prototype\s*\.",
    r"Object\.assign\s*\(",
]


def _is_private_host(host: str) -> bool:
    """Return True if host is a private/reserved IP."""
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


# ─── Token Bucket ─────────────────────────────────────────────────────────────

class TokenBucket:
    """
    Token bucket rate limiter.

    Args:
        capacity: Maximum number of tokens (requests).
        refill_rate: Tokens added per second (0.0 = no refill).
    """

    def __init__(self, capacity: float, refill_rate: float):
        self._capacity   = capacity
        self._tokens     = float(capacity)
        self._refill_rate = refill_rate
        self._last_refill = time.monotonic()
        self._used        = 0.0

    def _refill(self) -> None:
        if self._refill_rate <= 0:
            return
        now     = time.monotonic()
        elapsed = now - self._last_refill
        added   = elapsed * self._refill_rate
        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Attempt to consume tokens.

        Returns True if consumed, False if bucket is exhausted.
        """
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            self._used   += tokens
            return True
        return False

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens

    @property
    def used_tokens(self) -> float:
        return self._used

    @property
    def capacity(self) -> float:
        return self._capacity


# ─── Browser Security Validator ───────────────────────────────────────────────

class BrowserSecurityValidator:
    """
    Validates URLs, request headers, and JavaScript before browser use.
    Includes per-domain rate limiting via token buckets.
    """

    def __init__(
        self,
        rate_limit_per_domain: int = 10,
        rate_limit_window: int = 60,
    ):
        self._rate_limit_per_domain = rate_limit_per_domain
        self._rate_limit_window     = rate_limit_window
        # refill_rate = tokens per second = limit / window
        refill_rate = rate_limit_per_domain / max(rate_limit_window, 1)
        self._global_bucket = TokenBucket(rate_limit_per_domain, refill_rate)
        self._domain_buckets: Dict[str, TokenBucket] = {}

    # ── URL Validation ────────────────────────────────────────────────────────

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validate a URL for SSRF and other security issues.

        Returns (True, "ok") or (False, reason).
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return False, "Malformed URL"

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"Disallowed scheme: {scheme}"

        host = parsed.hostname or ""
        port = parsed.port

        # Block dangerous ports
        if port and port in _BLOCKED_PORTS:
            return False, f"Blocked port: {port}"

        # Block private/reserved IPs (SSRF protection)
        if _is_private_host(host):
            return False, f"Private/reserved host blocked: {host}"

        # Block localhost variants
        if host.lower() in ("localhost", "0.0.0.0"):
            return False, f"Localhost blocked: {host}"

        return True, "ok"

    # ── Header Validation ─────────────────────────────────────────────────────

    def validate_request_headers(self, headers: Dict[str, str]) -> Tuple[bool, str]:
        """
        Validate request headers for injection attacks.

        Blocks:
        - CRLF injection (\\r\\n)
        - Null byte injection (\\x00)
        - Host header spoofing
        """
        for name, value in headers.items():
            # CRLF injection
            if "\r" in value or "\n" in value:
                return False, f"CRLF injection in header '{name}'"
            # Null byte injection
            if "\x00" in value or "\x00" in name:
                return False, f"Null byte in header '{name}'"
            # Host header spoofing — Host must look like a valid FQDN or IP[:port]
            if name.lower() == "host":
                # Must contain a dot (FQDN) or be an IPv6 address in brackets,
                # or a bare numeric IPv4, or include a port after a colon.
                # Single bare words like "evil" or "localhost" are rejected.
                host_part = value.split(":")[0]  # strip port if present
                has_dot = "." in host_part
                is_ipv6 = host_part.startswith("[") and host_part.endswith("]")
                if not (has_dot or is_ipv6):
                    return False, f"Invalid Host header value: {value}"
                if not re.match(r"^[a-zA-Z0-9.\-_:\[\]]+$", value):
                    return False, f"Invalid Host header value: {value}"
        return True, "ok"

    # ── JavaScript Validation ────────────────────────────────────────────────

    def validate_javascript(self, js: str) -> Tuple[bool, str]:
        """
        Detect dangerous JavaScript patterns (prototype pollution, etc.).
        """
        for pattern in _JS_DANGEROUS_PATTERNS:
            if re.search(pattern, js):
                return False, f"Dangerous JS pattern: {pattern}"
        return True, "ok"

    # ── Rate Limiting ─────────────────────────────────────────────────────────

    def check_rate_limit(self, domain: str) -> Tuple[bool, str]:
        """Check domain-level rate limit. Returns (allowed, reason)."""
        if domain not in self._domain_buckets:
            refill_rate = self._rate_limit_per_domain / max(self._rate_limit_window, 1)
            self._domain_buckets[domain] = TokenBucket(
                self._rate_limit_per_domain, refill_rate
            )
        bucket = self._domain_buckets[domain]
        if bucket.consume():
            return True, "ok"
        return False, f"Rate limit exceeded for domain: {domain}"

    def get_token_status(self) -> Dict[str, float]:
        """Return global token bucket status."""
        return {
            "available": self._global_bucket.available_tokens,
            "used":      self._global_bucket.used_tokens,
            "capacity":  self._global_bucket.capacity,
        }
