"""
Lirox v2.0 — Browser Tool (Portable Edition)

Robust web access for research and data gathering.
Works on ANY device — no headless browser binary required.

Features:
- Real HTTP fetching with proper headers and retry logic
- DuckDuckGo search with proper URL unwrapping
- Google fallback search when DDG fails
- Source quality scoring
- Content extraction with BS4
- User-Agent rotation to avoid blocks
"""

import re
import time
import random
import logging
import requests
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from lirox.utils.errors import ToolExecutionError

logger = logging.getLogger("lirox.browser")

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ─── User-Agent Pool — rotate to avoid detection ─────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# Domains/patterns to block outright
BLOCKED_PATTERNS = [
    "malware", "phishing", "localhost", "127.0.0.1",
    "0.0.0.0", "192.168.", "10.0.", "172.16.",
]

# Maximum content size to process (5MB)
MAX_CONTENT_SIZE = 5 * 1024 * 1024

# High-quality source domains — used by score_source()
_HIGH_QUALITY_DOMAINS = {
    "github.com": 0.95,
    "arxiv.org": 0.95,
    "nature.com": 0.9,
    "scholar.google.com": 0.9,
    "pubmed.ncbi.nlm.nih.gov": 0.9,
    "stackoverflow.com": 0.88,
    "docs.python.org": 0.88,
    "developer.mozilla.org": 0.88,
    "docs.anthropic.com": 0.88,
    "openai.com": 0.85,
    "wikipedia.org": 0.85,
    "reuters.com": 0.92,
    "bloomberg.com": 0.92,
    "finance.yahoo.com": 0.90,
    "investing.com": 0.88,
    "marketwatch.com": 0.88,
    "cnbc.com": 0.88,
    "forbes.com": 0.85,
    "ft.com": 0.90,
    "wsj.com": 0.90,
    "nseindia.com": 0.95,
    "moneycontrol.com": 0.85,
    "coingecko.com": 0.88,
    "coinmarketcap.com": 0.88,
    "bbc.com": 0.82,
    "nytimes.com": 0.82,
    "techcrunch.com": 0.75,
    "medium.com": 0.65,
    "reddit.com": 0.60,
    "quora.com": 0.55,
}

# Financial/Real-time data indicators
_DATA_POINT_KEYWORDS = [
    "price", "price now", "value", "current", "live", "rate", "index", 
    "closing", "opening", "high", "low", "market cap", "volatility", "vix"
]

# Penalise spam/SEO-farm-like patterns
_LOW_QUALITY_SIGNALS = [
    "click", "trick", "secret", "earn", "make-money", "affiliate",
    "casino", "bet", "free-gift", "discount", "coupon",
]

# Search-engine domains to filter out of results
_SEARCH_ENGINES = {"duckduckgo.com", "google.com", "bing.com", "yahoo.com",
                   "yandex.com", "baidu.com"}


class BrowserTool:
    """Robust web access tool for fetching, parsing, and searching the web."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()

        # Connection pooling — reuse TCP connections across requests
        try:
            from requests.adapters import HTTPAdapter
            try:
                from urllib3.util.retry import Retry
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "HEAD"],
                )
            except ImportError:
                retry_strategy = None

            adapter = HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=retry_strategy or 3,
            )
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
            logger.debug("HTTP connection pooling enabled (10 connections)")
        except ImportError:
            logger.warning("HTTPAdapter not available — connection pooling disabled")

        self._rotate_ua()

    def _rotate_ua(self):
        """Set a fresh random User-Agent on the session."""
        ua = random.choice(_USER_AGENTS)
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

    # ─── URL Safety ──────────────────────────────────────────────────────────

    def is_url_safe(self, url):
        """Check if a URL is safe to fetch. Blocks internal/dangerous URLs."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                return False, "Only http/https URLs are allowed"

            full_url = url.lower()
            for pattern in BLOCKED_PATTERNS:
                if pattern in full_url:
                    return False, f"Blocked pattern detected: '{pattern}'"

            return True, "ok"
        except Exception:
            return False, "Invalid URL format"

    # ─── Core Fetching ───────────────────────────────────────────────────────

    def fetch_url(self, url, timeout=None, retries=2):
        """
        Safely fetch a URL and return its raw HTML content.
        Includes automatic retry with User-Agent rotation on failure.

        Raises ToolExecutionError on failure.
        """
        safe, reason = self.is_url_safe(url)
        if not safe:
            raise ToolExecutionError("browser", f"Unsafe URL: {reason}")

        last_error = None
        for attempt in range(retries + 1):
            try:
                if attempt > 0:
                    self._rotate_ua()
                    time.sleep(0.5 * attempt)

                response = self.session.get(
                    url,
                    timeout=timeout or self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
                response.raise_for_status()

                # Check content size before reading
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_CONTENT_SIZE:
                    raise ToolExecutionError(
                        "browser",
                        f"Content too large: {content_length} bytes",
                        is_retryable=False,
                    )

                return response.text[:MAX_CONTENT_SIZE]

            except ToolExecutionError:
                raise
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < retries:
                    continue
                from lirox.utils.errors import BrowserTimeoutError
                raise BrowserTimeoutError("fetching", url)
            except requests.exceptions.ConnectionError as e:
                last_error = e
                if attempt < retries:
                    continue
                raise ToolExecutionError("browser", f"Connection failed: {url}", is_retryable=True)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else "unknown"
                is_retryable = status in (429, 500, 502, 503, 504)
                if is_retryable and attempt < retries:
                    last_error = e
                    continue
                raise ToolExecutionError("browser", f"HTTP {status}: {url}", is_retryable=is_retryable)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    continue
                raise ToolExecutionError("browser", f"Error fetching {url}: {str(e)}")

        raise ToolExecutionError("browser", f"All retries failed for {url}: {last_error}")

    # ─── HTML Parsing ─────────────────────────────────────────────────────────

    def extract_text(self, html):
        """Extract clean readable text from HTML, stripping all tags."""
        if not html:
            return ""

        if not BeautifulSoup:
            clean = re.sub(r'<[^>]+>', ' ', html)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove script, style, and navigation elements
            for tag in soup(["script", "style", "nav", "footer", "header",
                           "aside", "noscript", "svg", "iframe"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
        except Exception:
            clean = re.sub(r'<[^>]+>', ' ', html)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean

    def extract_data(self, html: str, selector: str) -> list:
        """
        Extract text content from HTML elements matching a CSS selector.

        Args:
            html: HTML content string
            selector: CSS selector (e.g., '.item', '#header', 'div.content')

        Returns:
            List of text content from matching elements
        """
        if not html or not selector:
            return []

        if not BeautifulSoup:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(selector)
            return [elem.get_text(strip=True) for elem in elements]
        except Exception:
            return []

    def find_numeric_data(self, text: str, query: str = None) -> list:
        """
        Sophisticated extraction for financial/real-time data (prices, indices).
        Uses contextual regex to find numbers associated with the query.
        """
        if not text:
            return []
            
        found = []
        # 1. Look for currency symbols followed by numbers
        currency_patterns = [
            r'(?:[$\u20b9\u20ac\u00a3]|USD|INR|EUR|GBP)\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?',
            r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?(?:[$\u20b9\u20ac\u00a3]|USD|INR|EUR|GBP)',
        ]
        
        # 2. Look for percentage/point changes
        change_patterns = [
            r'[+-]?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?%',
            r'[+-]?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?(?:points|pts)',
        ]
        
        # 3. Contextual search if query is provided
        if query:
            # Extract keywords from query (e.g., "Bitcoin" from "What is Bitcoin price?")
            keywords = [k for k in query.split() if len(k) > 3 and k.lower() not in ["what", "price", "current", "index"]]
            for kw in keywords[:2]:
                # Find number near the keyword (within 50 chars)
                context_pattern = rf'{re.escape(kw)}.*?(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)'
                matches = re.finditer(context_pattern, text, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    if len(m.group(0)) < 100: # Ensure they are close
                        found.append(f"{kw}: {m.group(1)}")

        for p in currency_patterns + change_patterns:
            matches = re.finditer(p, text, re.IGNORECASE)
            for m in matches:
                found.append(m.group(0))
                
        # Deduplicate and prioritize contextual over raw
        return list(dict.fromkeys(found))[:8]

    def fetch_verified_data(self, query: str, search_query: str = None) -> dict:
        """
        Phase 1: Professional verified data retrieval.
        Searches, fetches top results, and verifies if the desired data point exists.
        """
        search_q = search_query or query
        if not any(k in query.lower() for k in _DATA_POINT_KEYWORDS):
            # Normal research synthesis if not a specific data point
            return self.research_topic(search_q)

        results = self.search_web(search_q, num_results=5)
        if not results:
            return {
                "error": "No results found", 
                "type": "failure", 
                "content": f"No search results found for '{search_q}'."
            }

        # Try to find the answer in the first 3 reliable sources
        attempts = []
        for i, res in enumerate(results[:3]):
            try:
                html = self.fetch_url(res["url"])
                text = self.extract_text(html)
                # Take snippet + first 2k chars
                context = (res["snippet"] + "\n" + text)[:2500]
                data_points = self.find_numeric_data(context, query)
                
                if data_points:
                    return {
                        "content": f"Found real-time data for '{query}' at {res['domain']}:\n" + "\n".join([f"- {dp}" for dp in data_points]),
                        "sources": [res],
                        "data_points": data_points,
                        "type": "verified_data"
                    }
                attempts.append(f"Scanned {res['domain']} - no specific match.")
            except Exception as e:
                attempts.append(f"Failed to access {res['domain']}: {str(e)}")

        return {
            "content": f"Searched for '{query}' but could not verify live data point in top sources.\n" + "\n".join(attempts),
            "sources": results[:2],
            "type": "unverified_data"
        }

    # ─── URL Unwrapping ──────────────────────────────────────────────────────

    @staticmethod
    def _unwrap_ddg_url(url: str) -> str:
        """
        Unwrap DuckDuckGo redirect URLs to get the actual destination URL.
        Handles multiple DDG redirect formats.
        """
        if not url:
            return url

        # Format 1: //duckduckgo.com/l/?uddg=ENCODED_URL&...
        if "uddg=" in url:
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                real_urls = qs.get("uddg", [])
                if real_urls:
                    return unquote(real_urls[0])
            except Exception:
                pass

        # Format 2: /y.js?ad_domain=... (DDG ads — extract ad_domain)
        if "/y.js?" in url and "ad_domain=" in url:
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                ad_domain = qs.get("ad_domain", [""])[0]
                if ad_domain:
                    return f"https://{ad_domain}"
            except Exception:
                pass

        # Format 3: duckduckgo.com redirect with rut parameter
        if "duckduckgo.com" in url and "rut=" in url:
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                rut_urls = qs.get("rut", [])
                if rut_urls:
                    return unquote(rut_urls[0])
            except Exception:
                pass

        return url

    @staticmethod
    def _is_real_result_url(url: str) -> bool:
        """Check if a URL is a real destination (not a search engine redirect)."""
        if not url or not url.startswith("http"):
            return False
        domain = urlparse(url).netloc.replace("www.", "").lower()
        # Reject search engine domains and internal DDG URLs
        if domain in _SEARCH_ENGINES:
            return False
        if "/y.js?" in url:
            return False
        return True

    # ─── Web Search ──────────────────────────────────────────────────────────

    def search_web(self, query, num_results=5):
        """
        Search the web using DuckDuckGo HTML (no API key required).
        Returns list of rich source objects with title, url, snippet, domain, icon.

        Properly unwraps all DDG redirect URLs.
        """
        results = self._search_duckduckgo(query, num_results)

        # If DDG returned too few results, try Google scrape fallback
        if len(results) < 2:
            logger.info("DDG returned < 2 results, trying Google fallback")
            google_results = self._search_google_fallback(query, num_results)
            results.extend(google_results)

        # Deduplicate by domain
        seen_domains = set()
        deduped = []
        for r in results:
            d = r.get("domain", "")
            if d and d not in seen_domains:
                seen_domains.add(d)
                deduped.append(r)
            elif not d:
                deduped.append(r)
        
        return deduped[:num_results]

    def _search_duckduckgo(self, query, num_results=5):
        """Search DuckDuckGo HTML — no API key required."""
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            self._rotate_ua()
            html = self.fetch_url(search_url, timeout=15)
        except ToolExecutionError as e:
            logger.warning(f"DDG search failed: {e}")
            return []

        if not BeautifulSoup:
            return [{"title": "Error", "url": "", "snippet": "BS4 missing", "domain": "error"}]

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for result in soup.select(".result"):
            title_el = result.select_one(".result__a")
            snippet_el = result.select_one(".result__snippet")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            raw_url = title_el.get("href", "")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            # Unwrap DDG redirect URL
            url = self._unwrap_ddg_url(raw_url)

            # Skip if still a search engine URL after unwrapping
            if not self._is_real_result_url(url):
                continue

            domain = urlparse(url).netloc.replace("www.", "")
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "domain": domain,
                "icon": f"https://www.google.com/s2/favicons?sz=64&domain={domain}",
                "score": self.score_source(url),
            })

            if len(results) >= num_results:
                break

        return results

    def _search_google_fallback(self, query, num_results=5):
        """Fallback: scrape Google search results page."""
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results + 5}"

        try:
            self._rotate_ua()
            html = self.fetch_url(search_url, timeout=15)
        except ToolExecutionError:
            return []

        if not BeautifulSoup:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Google wraps results in <a> tags with href starting with /url?q=
        for a_tag in soup.select("a"):
            href = a_tag.get("href", "")

            # Google result links
            real_url = None
            if href.startswith("/url?q="):
                try:
                    qs = parse_qs(urlparse(href).query)
                    real_url = qs.get("q", [""])[0]
                except Exception:
                    continue
            elif href.startswith("https://") and "google.com" not in href:
                real_url = href

            if not real_url or not self._is_real_result_url(real_url):
                continue

            title = a_tag.get_text(strip=True) or ""
            if not title or len(title) < 5:
                continue

            domain = urlparse(real_url).netloc.replace("www.", "")
            results.append({
                "title": title,
                "url": real_url,
                "snippet": "",
                "domain": domain,
                "icon": f"https://www.google.com/s2/favicons?sz=64&domain={domain}",
                "score": self.score_source(real_url),
            })

            if len(results) >= num_results:
                break

        return results

    # ─── Source Quality Scoring ───────────────────────────────────────────────

    def score_source(self, url: str) -> float:
        """
        Rate the quality/credibility of a source URL on a 0.0–1.0 scale.

        Scores are based on:
        - Domain reputation whitelist
        - URL path length heuristic (shorter = cleaner)
        - Low-quality signal detection (spam/SEO keywords)

        Returns a float between 0.0 (poor) and 1.0 (excellent).
        """
        if not url or not url.startswith("http"):
            return 0.0

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")

            # 1. Check high-quality domain whitelist
            for known_domain, score in _HIGH_QUALITY_DOMAINS.items():
                if domain == known_domain or domain.endswith(f".{known_domain}"):
                    return score

            # 2. Penalise low-quality signals in the full URL
            full_url_lower = url.lower()
            for signal in _LOW_QUALITY_SIGNALS:
                if signal in full_url_lower:
                    return 0.2

            # 3. Prefer shorter paths (less likely to be deep SEO pages)
            path_depth = len([p for p in parsed.path.split("/") if p])
            if path_depth <= 1:
                base_score = 0.72
            elif path_depth <= 3:
                base_score = 0.65
            else:
                base_score = 0.55

            # 4. Penalise query-string-heavy URLs
            if len(parsed.query) > 100:
                base_score -= 0.1

            # 5. Favour HTTPS over HTTP
            if parsed.scheme != "https":
                base_score -= 0.05

            return max(0.0, min(1.0, base_score))

        except Exception:
            return 0.3  # default mid-low score on parse error

    # ─── Deep Research ────────────────────────────────────────────────────────

    def research_topic(self, query):
        """
        Deep research: search, rank sources, fetch top pages, and synthesize.
        Returns a dict with 'content', 'sources', and 'type'.
        """
        results = self.search_web(query, num_results=8)
        if not results:
            return {"content": "No search results found.", "sources": []}

        # Sort by pre-computed score
        sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        top_sources = sorted_results[:4]

        synthesis_input = [f"Focus Query: {query}\n"]
        for i, res in enumerate(top_sources, 1):
            synthesis_input.append(f"Source {i} ({res['domain']}) — quality score {res['score']:.2f}:")
            content = self.summarize_page(res["url"])
            synthesis_input.append(content[:1800])
            synthesis_input.append("-" * 20)

        return {
            "content": "\n".join(synthesis_input),
            "sources": top_sources,
            "type": "research_synthesis",
        }

    def summarize_page(self, url):
        """
        Fetch a URL, extract text, and truncate to a reasonable LLM context size.
        """
        try:
            html = self.fetch_url(url)
            text = self.extract_text(html)
            if not text or len(text) < 50:
                return f"[Page at {url} returned minimal content — may require JavaScript]"
            return text[:4000] if len(text) > 4000 else text
        except ToolExecutionError as e:
            return f"Error accessing {url}: {str(e)}"

    def extract_urls_from_text(self, text: str) -> list:
        """
        Extract clean https URLs from a text string.
        Filters out search engine URLs.
        """
        if not text:
            return []

        raw_urls = re.findall(r'https?://[^\s\)\>"\'>]+', text)
        seen = set()
        clean = []
        for url in raw_urls:
            url = url.rstrip(".,;)>\"'")
            if not self._is_real_result_url(url):
                continue
            if url not in seen:
                seen.add(url)
                clean.append(url)
        return clean
