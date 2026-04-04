"""
Lirox v2.0 — Browser Security & Validation (Hardened)

Production-grade security layer for browser operations:
- SSRF protection (cloud metadata, private IPs, IPv6, blocked ports)
- Header injection prevention (CRLF, NULL bytes, sensitive overrides)
- Token bucket rate limiting with live token tracking
- JavaScript & CSS selector sanitization
- Data extraction validation (financial/live data)
"""

import re
import json
import time
import logging
from enum import Enum
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

logger = logging.getLogger("lirox.browser.security")

# ─── Domain & IP Blocklists ──────────────────────────────────────────────────

BLOCKED_DOMAINS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",   # AWS metadata
    "169.254.169.253",   # Azure metadata (IMDS wireserver)
    "metadata.google.internal",  # GCP metadata
    "metadata.internal",
}

BLOCKED_IP_PREFIXES = [
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
    "fc00:",   # IPv6 unique local
    "fe80:",   # IPv6 link-local
    "fd",      # IPv6 ULA
]

BLOCKED_SCHEMES = {"javascript", "data", "file", "ftp", "vbscript", "blob"}

# Ports that should never be accessed via browser automation
BLOCKED_PORTS = {
    22, 23, 25, 109, 110, 143,    # SSH, Telnet, SMTP, POP2/3, IMAP
    465, 587, 993, 995,            # SMTPS, Submission, IMAPS, POP3S
    3306, 5432, 6379, 27017,       # MySQL, Postgres, Redis, MongoDB
}

# Dangerous JS APIs that browser scripts should never call
DANGEROUS_JS_PATTERNS = [
    r"chrome\.\w+",
    r"window\.open\s*\(",
    r"window\.close\s*\(",
    r"document\.write\s*\(",
    r"eval\s*\(",
    r"Function\s*\(",
    r"setTimeout\s*\(\s*['\"]",
    r"setInterval\s*\(\s*['\"]",
    r"\.innerHTML\s*=",
    r"importScripts\s*\(",
    r"XMLHttpRequest",
    r"fetch\s*\(\s*['\"](?!https?://)",
    r"__proto__",
    r"constructor\s*\[",
    r"\.prototype\s*=",
    r"new\s+WebSocket\s*\(",
    r"navigator\.sendBeacon\s*\(",
    r"ServiceWorker",
]

# Headers that must not be overridden by user-supplied values
PROTECTED_HEADERS = {
    "host", "authorization", "cookie", "set-cookie",
    "proxy-authorization", "proxy-authenticate",
    "transfer-encoding", "content-length",
}


# ─── Rate Limit Strategy ─────────────────────────────────────────────────────

class RateLimitStrategy(Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"


class TokenBucket:
    """
    Token bucket rate limiter — allows controlled bursts while
    maintaining long-term rate compliance.

    Exposes `available_tokens` and `used_tokens` for UI display.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens the bucket can hold
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.time()
        self._total_consumed = 0

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            self._total_consumed += tokens
            return True
        return False

    @property
    def available_tokens(self) -> int:
        """Current tokens available (for UI display)."""
        self._refill()
        return int(self._tokens)

    @property
    def used_tokens(self) -> int:
        """Total tokens consumed since creation (for UI display)."""
        return self._total_consumed

    @property
    def capacity_max(self) -> int:
        """Maximum capacity (for UI display)."""
        return self.capacity


class BrowserSecurityValidator:
    """
    Validate all browser inputs to prevent injection and SSRF attacks.

    Usage:
        validator = BrowserSecurityValidator()
        is_safe, reason = validator.validate_url("https://example.com")
        tokens = validator.get_token_status()  # For UI display
    """

    def __init__(self, custom_blocklist: List[str] = None,
                 rate_limit_per_domain: int = 10,
                 rate_limit_window: int = 60,
                 strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET):
        self.custom_blocklist = set(custom_blocklist or [])
        self.rate_limit_per_domain = rate_limit_per_domain
        self.rate_limit_window = rate_limit_window
        self.strategy = strategy

        # Token bucket per domain (capacity = per_domain limit, refill = capacity/window)
        self._domain_buckets: Dict[str, TokenBucket] = {}

        # Global token bucket for overall rate tracking
        global_capacity = rate_limit_per_domain * 10  # 100 tokens default
        self._global_bucket = TokenBucket(
            capacity=global_capacity,
            refill_rate=global_capacity / rate_limit_window
        )

        # Sliding window fallback
        self._domain_request_times: Dict[str, List[float]] = defaultdict(list)

    # ─── URL Validation ───────────────────────────────────────────────────────

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validate URL is safe for browser navigation.

        Returns:
            (is_safe: bool, reason: str)
        """
        if not url or not isinstance(url, str):
            return False, "URL is empty or invalid type"

        url = url.strip()
        if len(url) > 2048:
            return False, "URL exceeds maximum length (2048 chars)"

        try:
            parsed = urlparse(url)
        except Exception:
            return False, "Failed to parse URL"

        # Scheme validation
        scheme = (parsed.scheme or "").lower()
        if not scheme:
            return False, "URL missing scheme (require http:// or https://)"
        if scheme in BLOCKED_SCHEMES:
            return False, f"Blocked scheme: {scheme}"
        if scheme not in ("http", "https"):
            return False, f"Only http/https allowed, got: {scheme}"

        # Host validation
        host = (parsed.hostname or "").lower()
        if not host:
            return False, "URL has no hostname"

        # Check blocklists
        if host in BLOCKED_DOMAINS or host in self.custom_blocklist:
            return False, f"Blocked domain: {host}"

        for prefix in BLOCKED_IP_PREFIXES:
            if host.startswith(prefix):
                return False, f"Private/internal IP range blocked: {host}"

        # Check for IP-based bypasses (decimal encoding, hex encoding)
        if re.match(r"^\d+$", host):
            return False, "Numeric IP (decimal) not allowed"
        if host.startswith("0x"):
            return False, "Hex-encoded IP not allowed"
        # Octal encoding: 0177.0.0.1
        if re.match(r"^0\d+\.", host):
            return False, "Octal-encoded IP not allowed"

        # Port blocking
        port = parsed.port
        if port and port in BLOCKED_PORTS:
            return False, f"Blocked port: {port} (security policy)"

        # Rate limiting
        if not self._check_rate_limit(host):
            return False, f"Rate limit exceeded for domain: {host}"

        return True, "ok"

    def _check_rate_limit(self, domain: str) -> bool:
        """Check if domain is within rate limits using configured strategy."""
        if self.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return self._check_token_bucket(domain)
        else:
            return self._check_sliding_window(domain)

    def _check_token_bucket(self, domain: str) -> bool:
        """Token bucket rate limiting — allows bursts, tracks usage."""
        if domain not in self._domain_buckets:
            self._domain_buckets[domain] = TokenBucket(
                capacity=self.rate_limit_per_domain,
                refill_rate=self.rate_limit_per_domain / self.rate_limit_window
            )

        domain_ok = self._domain_buckets[domain].consume(1)
        global_ok = self._global_bucket.consume(1)

        if not domain_ok:
            logger.warning(f"Rate limit (domain): {domain}")
        if not global_ok:
            logger.warning(f"Rate limit (global) exceeded")

        return domain_ok and global_ok

    def _check_sliding_window(self, domain: str) -> bool:
        """Sliding window rate limiting — strict, no bursts."""
        now = time.time()
        cutoff = now - self.rate_limit_window

        self._domain_request_times[domain] = [
            t for t in self._domain_request_times[domain] if t > cutoff
        ]

        if len(self._domain_request_times[domain]) >= self.rate_limit_per_domain:
            return False

        self._domain_request_times[domain].append(now)
        return True

    # ─── Token Status (For UI) ────────────────────────────────────────────────

    def get_token_status(self) -> Dict[str, Any]:
        """
        Get current token usage status for UI header display.

        Returns:
            {
                "available": int,
                "used": int,
                "capacity": int,
                "domains_tracked": int,
                "strategy": str,
            }
        """
        return {
            "available": self._global_bucket.available_tokens,
            "used": self._global_bucket.used_tokens,
            "capacity": self._global_bucket.capacity_max,
            "domains_tracked": len(self._domain_buckets),
            "strategy": self.strategy.value,
        }

    # ─── Header Validation ────────────────────────────────────────────────────

    def validate_request_headers(self, headers: Dict[str, str]) -> Tuple[bool, str]:
        """
        Validate HTTP request headers for injection attacks.

        Blocks:
        - CRLF injection (\\r\\n in values)
        - NULL byte injection (\\x00)
        - Protected header overrides (Host, Authorization, etc.)

        Returns:
            (is_safe: bool, reason: str)
        """
        if not headers or not isinstance(headers, dict):
            return True, "ok"  # No headers to validate

        for key, value in headers.items():
            key_lower = key.lower().strip()

            # Block protected header overrides
            if key_lower in PROTECTED_HEADERS:
                return False, f"Cannot override protected header: {key}"

            # Check for CRLF injection
            if "\r" in str(value) or "\n" in str(value):
                return False, f"CRLF injection detected in header '{key}'"

            # Check for NULL byte injection
            if "\x00" in str(key) or "\x00" in str(value):
                return False, f"NULL byte injection detected in header '{key}'"

            # Check for excessively long header values
            if len(str(value)) > 8192:
                return False, f"Header value too long for '{key}' ({len(str(value))} chars)"

        return True, "ok"

    # ─── Selector Validation ──────────────────────────────────────────────────

    def validate_selector(self, selector: str) -> Tuple[bool, str]:
        """
        Validate CSS/XPath selector is safe.

        Returns:
            (is_safe: bool, reason: str)
        """
        if not selector or not isinstance(selector, str):
            return False, "Selector is empty or invalid type"

        selector = selector.strip()
        if len(selector) > 1000:
            return False, "Selector exceeds maximum length (1000 chars)"

        # Block potential injection patterns
        dangerous_patterns = [
            r"<\s*script",
            r"javascript:",
            r"on\w+\s*=",
            r"\}\s*\{",
            r";\s*\w+\s*:",
            r"__proto__",
            r"constructor\s*\[",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, selector, re.IGNORECASE):
                return False, "Potentially dangerous pattern in selector"

        return True, "ok"

    # ─── JavaScript Validation ────────────────────────────────────────────────

    def validate_javascript(self, script: str) -> Tuple[bool, str]:
        """
        Validate JavaScript code is safe for in-page evaluation.

        Returns:
            (is_safe: bool, reason: str)
        """
        if not script or not isinstance(script, str):
            return False, "Script is empty or invalid type"

        if len(script) > 10240:
            return False, "Script exceeds maximum length (10KB)"

        for pattern in DANGEROUS_JS_PATTERNS:
            if re.search(pattern, script, re.IGNORECASE):
                return False, f"Dangerous API detected in script"

        return True, "ok"


class DataValidator:
    """Validate quality and structure of data extracted from pages."""

    @staticmethod
    def validate_table(table: List[List[Dict]]) -> Tuple[bool, str]:
        """
        Validate extracted table data has consistent structure.

        Returns:
            (is_valid: bool, reason: str)
        """
        if not table or not isinstance(table, list):
            return False, "Table is empty or invalid type"

        if len(table) == 0:
            return False, "Table has no rows"

        # Check first row for column structure
        first_row = table[0]
        if not isinstance(first_row, (list, dict)):
            return False, "Invalid row format"

        if isinstance(first_row, list):
            col_count = len(first_row)
            for i, row in enumerate(table[1:], 1):
                if not isinstance(row, list):
                    return False, f"Row {i} is not a list"
                if len(row) != col_count:
                    return False, f"Row {i} has {len(row)} cols, expected {col_count}"

        # Check for completely empty table
        all_empty = True
        for row in table:
            if isinstance(row, list):
                if any(str(v).strip() for v in row):
                    all_empty = False
                    break
            elif isinstance(row, dict):
                if any(str(v).strip() for v in row.values()):
                    all_empty = False
                    break

        if all_empty:
            return False, "Table contains only empty values"

        return True, "ok"

    @staticmethod
    def validate_links(links: List[Dict]) -> Tuple[bool, str]:
        """
        Validate extracted link data.

        Returns:
            (is_valid: bool, reason: str)
        """
        if not links or not isinstance(links, list):
            return False, "Links list is empty or invalid"

        valid_count = 0
        for link in links:
            if not isinstance(link, dict):
                continue
            url = link.get("url", "")
            if url and (url.startswith("http") or url.startswith("/")):
                valid_count += 1

        if valid_count == 0:
            return False, "No valid URLs found in links"

        return True, "ok"

    @staticmethod
    def validate_json_from_page(json_str: str) -> Tuple[Optional[Any], Optional[str]]:
        """
        Parse and validate JSON extracted from a page.

        Returns:
            (parsed_data: Optional[dict|list], error: Optional[str])
        """
        if not json_str or not isinstance(json_str, str):
            return None, "Empty or invalid JSON string"

        try:
            data = json.loads(json_str)
            return data, None
        except json.JSONDecodeError as e:
            return None, f"JSON parse error: {str(e)}"

    @staticmethod
    def validate_stock_price(data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate extracted stock/financial data.

        Returns:
            (is_valid: bool, reason: str)
        """
        if not data or not isinstance(data, dict):
            return False, "Data is empty or invalid"

        price_field = data.get("current_price") or data.get("price")
        if not price_field:
            return False, "No price field found"

        try:
            # Clean price string
            clean = str(price_field).replace(",", "").replace("$", "").replace("₹", "").strip()
            price = float(clean)
            if price <= 0:
                return False, f"Price is non-positive: {price}"
            if price > 10_000_000:
                return False, f"Price seems unreasonably high: {price}"
            return True, "ok"
        except (ValueError, TypeError):
            return False, f"Cannot parse price: {price_field}"
