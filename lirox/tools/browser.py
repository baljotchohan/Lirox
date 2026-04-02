"""
Lirox v0.5 — Browser Tool

Lightweight web access for research and data gathering.
Uses requests + BeautifulSoup (no headless browser needed).

Fixes from v0.4:
- Added missing score_source() method (was causing crash in research_topic)
- Improved URL extraction with better cleaning
- Increased timeout to 15s
"""

import re
import requests
from urllib.parse import quote_plus, urlparse
from lirox.utils.errors import ToolExecutionError

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


# User-Agent to avoid bot blocking on most sites
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

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
    "reuters.com": 0.85,
    "bbc.com": 0.82,
    "nytimes.com": 0.82,
    "techcrunch.com": 0.75,
    "medium.com": 0.65,
    "reddit.com": 0.60,
    "quora.com": 0.55,
}

# Penalise spam/SEO-farm-like patterns
_LOW_QUALITY_SIGNALS = [
    "click", "trick", "secret", "earn", "make-money", "affiliate",
    "casino", "bet", "free-gift", "discount", "coupon",
]


class BrowserTool:
    """Lightweight web access tool for fetching, parsing, and searching the web."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
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

    def fetch_url(self, url, timeout=None):
        """
        Safely fetch a URL and return its raw HTML content.

        Raises ToolExecutionError on failure.
        """
        safe, reason = self.is_url_safe(url)
        if not safe:
            raise ToolExecutionError("browser", f"Unsafe URL: {reason}")

        try:
            response = self.session.get(
                url,
                timeout=timeout or self.timeout,
                allow_redirects=True,
                stream=True
            )
            response.raise_for_status()

            # Check content size before reading
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_CONTENT_SIZE:
                raise ToolExecutionError(
                    "browser",
                    f"Content too large: {content_length} bytes",
                    is_retryable=False
                )

            return response.text[:MAX_CONTENT_SIZE]

        except ToolExecutionError:
            raise
        except requests.exceptions.Timeout:
            raise ToolExecutionError("browser", f"Timeout fetching {url}", is_retryable=True)
        except requests.exceptions.ConnectionError:
            raise ToolExecutionError("browser", f"Connection failed: {url}", is_retryable=True)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "unknown"
            is_retryable = status in (429, 500, 502, 503, 504)
            raise ToolExecutionError("browser", f"HTTP {status}: {url}", is_retryable=is_retryable)
        except Exception as e:
            raise ToolExecutionError("browser", f"Error fetching {url}: {str(e)}")

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
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
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

    def find_numeric_data(self, text: str, labels: list = None) -> list:
        """
        Specialized extraction for financial/real-time data (prices, indices).
        Looks for patterns like 'Nifty 50: 22,000' or '$50.00'.
        """
        if not text: return []
        patterns = [
            r'(\$|₹|USD|INR)\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?', # Currency
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?(points|%)'     # Percentage/Points
        ]
        if labels:
            for label in labels:
                patterns.append(rf'{re.escape(label)}[:\s-]+(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)')

        found = []
        for p in patterns:
            matches = re.finditer(p, text, re.IGNORECASE)
            for m in matches:
                found.append(m.group(0))
        return list(set(found))[:5]

    # ─── Web Search ──────────────────────────────────────────────────────────

    def search_web(self, query, num_results=5):
        """
        Search the web using DuckDuckGo HTML (no API key required).
        Returns list of rich source objects with title, url, snippet, domain, icon.
        """
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            html = self.fetch_url(search_url, timeout=15)
        except ToolExecutionError:
            return []

        if not BeautifulSoup:
            return [{"title": "Error", "url": "", "snippet": "BS4 missing", "domain": "error"}]

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for result in soup.select(".result"):
            title_el   = result.select_one(".result__a")
            snippet_el = result.select_one(".result__snippet")

            if title_el:
                title   = title_el.get_text(strip=True)
                url     = title_el.get("href", "")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # Unwrap DuckDuckGo redirect URLs
                if "uddg=" in url:
                    try:
                        from urllib.parse import parse_qs, urlparse as up
                        real_url = parse_qs(up(url).query).get("uddg", [url])[0]
                        url = real_url
                    except Exception:
                        pass

                domain = urlparse(url).netloc.replace("www.", "")
                results.append({
                    "title":   title,
                    "url":     url,
                    "snippet": snippet,
                    "domain":  domain,
                    "icon":    f"https://www.google.com/s2/favicons?sz=64&domain={domain}",
                    "score":   self.score_source(url),
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

        raw_urls = re.findall(r'https?://[^\s\)\>"\']+', text)
        SEARCH_ENGINES = {"duckduckgo.com", "google.com", "bing.com", "yahoo.com"}
        seen = set()
        clean = []
        for url in raw_urls:
            url = url.rstrip(".,;)>\"'")
            domain = urlparse(url).netloc.replace("www.", "")
            if domain not in SEARCH_ENGINES and url not in seen:
                seen.add(url)
                clean.append(url)
        return clean
