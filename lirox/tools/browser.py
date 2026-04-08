"""
Lirox v2.0 — Browser Tool

Safe web browsing with:
- URL safety validation (blocks localhost, private IPs, non-HTTP)
- HTML text extraction and CSS selector support
- Web search via DuckDuckGo HTML
- Connection pooling via requests.Session
"""

from __future__ import annotations

import re
import ipaddress
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

# ─── URL Safety ──────────────────────────────────────────────────────────────

# Private/reserved IP ranges that should never be accessed
_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_BLOCKED_HOSTNAMES = {"localhost", "0.0.0.0", "::1"}

_ALLOWED_SCHEMES = {"http", "https"}


def _is_private_ip(host: str) -> bool:
    """Return True if host resolves to a private/reserved address."""
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _BLOCKED_IP_NETWORKS)
    except ValueError:
        return False  # Not an IP address — OK


class BrowserTool:
    """Safe HTTP browser with pooled connections."""

    def __init__(self, pool_connections: int = 10, pool_maxsize: int = 20, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=2,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({"User-Agent": "Lirox/2.0 (+https://lirox.ai)"})

    # ── URL Safety ────────────────────────────────────────────────────────────

    def is_url_safe(self, url: str) -> Tuple[bool, str]:
        """
        Check if a URL is safe to fetch.

        Returns (True, "ok") for safe URLs, (False, reason) for blocked ones.
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return False, "Invalid URL"

        scheme = parsed.scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            return False, f"Scheme '{scheme}' not allowed (only http/https)"

        host = parsed.hostname or ""
        host_lower = host.lower()

        if host_lower in _BLOCKED_HOSTNAMES:
            return False, f"Blocked host: {host}"

        if _is_private_ip(host):
            return False, f"Private/reserved IP address: {host}"

        # Block internal domain patterns
        if host_lower.endswith(".local") or host_lower.endswith(".internal"):
            return False, f"Internal domain blocked: {host}"

        return True, "ok"

    # ── Content Extraction ────────────────────────────────────────────────────

    def extract_text(self, html: str) -> str:
        """Strip HTML tags and return clean text."""
        if _BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        else:
            # Fallback: simple regex tag stripping
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_data(self, html: str, selector: str) -> List[str]:
        """Extract text content from elements matching a CSS selector."""
        if not _BS4_AVAILABLE:
            return []
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(selector)
        return [el.get_text(strip=True) for el in elements]

    # ── Fetching ──────────────────────────────────────────────────────────────

    def fetch_url(self, url: str) -> str:
        """Fetch a URL and return its raw HTML content."""
        safe, reason = self.is_url_safe(url)
        if not safe:
            raise ValueError(f"URL blocked: {reason}")
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            raise RuntimeError(f"Fetch failed: {e}") from e

    # ── Web Search ────────────────────────────────────────────────────────────

    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Search the web using DuckDuckGo HTML interface.

        Returns list of {"title": ..., "url": ..., "snippet": ...} dicts.
        """
        url = "https://html.duckduckgo.com/html/"
        try:
            html = self.fetch_url(url + f"?q={requests.utils.quote(query)}")
        except Exception:
            # fetch_url may raise; return empty on error
            html = ""

        results = self._parse_search_results(html, max_results)
        return results

    def _parse_search_results(self, html: str, max_results: int) -> List[Dict[str, str]]:
        """Parse DuckDuckGo HTML search results."""
        if not _BS4_AVAILABLE or not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for result_div in soup.select(".result"):
            if len(results) >= max_results:
                break
            title_el   = result_div.select_one(".result__a")
            snippet_el = result_div.select_one(".result__snippet")

            if not title_el:
                continue

            title   = title_el.get_text(strip=True)
            href    = title_el.get("href", "")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            if title:
                results.append({"title": title, "url": href, "snippet": snippet})

        return results
