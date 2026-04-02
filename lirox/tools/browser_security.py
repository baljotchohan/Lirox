"""
Lirox v0.7 — Browser Security & Validation

Input validation for URLs, CSS selectors, and JavaScript.
Output validation for extracted data quality.
Prevents injection attacks, SSRF, and data integrity issues.
"""

import re
import json
import time
from enum import Enum
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any
from collections import defaultdict


# ─── Domain Blocklist ─────────────────────────────────────────────────────────

BLOCKED_DOMAINS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",  # AWS metadata endpoint
    "metadata.google.internal",  # GCP metadata
}

BLOCKED_IP_PREFIXES = [
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
]

BLOCKED_SCHEMES = {"javascript", "data", "file", "ftp", "vbscript"}

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
]


class BrowserSecurityValidator:
    """Validate all browser inputs to prevent injection and SSRF attacks."""

    def __init__(self, custom_blocklist: List[str] = None,
                 rate_limit_per_domain: int = 10,
                 rate_limit_window: int = 60):
        self.custom_blocklist = set(custom_blocklist or [])
        self.rate_limit_per_domain = rate_limit_per_domain
        self.rate_limit_window = rate_limit_window
        self._domain_request_times: Dict[str, List[float]] = defaultdict(list)

    # ─── URL Validation ───────────────────────────────────────────────────────

    def validate_url(self, url: str) -> tuple:
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
                return False, f"Private IP range blocked: {host}"

        # Check for IP-based bypasses
        if re.match(r"^\d+$", host):
            return False, "Numeric IP (decimal) not allowed"
        if host.startswith("0x"):
            return False, "Hex-encoded IP not allowed"

        # Rate limiting
        if not self._check_rate_limit(host):
            return False, f"Rate limit exceeded for domain: {host}"

        return True, "ok"

    def _check_rate_limit(self, domain: str) -> bool:
        """Check if domain is within rate limits."""
        now = time.time()
        cutoff = now - self.rate_limit_window

        # Prune old entries
        self._domain_request_times[domain] = [
            t for t in self._domain_request_times[domain] if t > cutoff
        ]

        if len(self._domain_request_times[domain]) >= self.rate_limit_per_domain:
            return False

        self._domain_request_times[domain].append(now)
        return True

    # ─── Selector Validation ──────────────────────────────────────────────────

    def validate_selector(self, selector: str) -> tuple:
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
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, selector, re.IGNORECASE):
                return False, f"Potentially dangerous pattern in selector"

        return True, "ok"

    # ─── JavaScript Validation ────────────────────────────────────────────────

    def validate_javascript(self, script: str) -> tuple:
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
    def validate_table(table: List[List[Dict]]) -> tuple:
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
    def validate_links(links: List[Dict]) -> tuple:
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
    def validate_json_from_page(json_str: str) -> tuple:
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
    def validate_stock_price(data: Dict[str, Any]) -> tuple:
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
