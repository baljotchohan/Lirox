"""
Lirox v0.3 — Browser Tool

Lightweight web access for research and data gathering.
Uses requests + BeautifulSoup (no headless browser needed).
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
    "Chrome/120.0.0.0 Safari/537.36"
)

# Domains/patterns to block outright
BLOCKED_PATTERNS = [
    "malware", "phishing", "localhost", "127.0.0.1",
    "0.0.0.0", "192.168.", "10.0.", "172.16.",
]

# Maximum content size to process (5MB)
MAX_CONTENT_SIZE = 5 * 1024 * 1024


class BrowserTool:
    """Lightweight web access tool for fetching, parsing, and searching the web."""

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

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

    def fetch_url(self, url, timeout=None):
        """
        Safely fetch a URL and return its raw HTML content.

        Args:
            url: The URL to fetch
            timeout: Override default timeout

        Returns:
            Raw HTML string

        Raises:
            ToolExecutionError on failure
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

    def extract_text(self, html):
        """Extract clean readable text from HTML, stripping all tags."""
        if not BeautifulSoup:
            # Fallback: basic regex tag stripping
            clean = re.sub(r'<[^>]+>', ' ', html)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean

        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, and nav elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def extract_data(self, html, selector):
        """
        Extract structured data from HTML using a CSS selector.

        Args:
            html: Raw HTML string
            selector: CSS selector string (e.g., "h2.title", ".article-body p")

        Returns:
            List of text content from matching elements
        """
        if not BeautifulSoup:
            return ["Error: beautifulsoup4 not installed. Run: pip install beautifulsoup4"]

        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(selector)
        return [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]

    def search_web(self, query, num_results=5):
        """
        Search the web using DuckDuckGo HTML (no API key required).

        Args:
            query: Search query string
            num_results: Max number of results to return

        Returns:
            List of dicts: [{"title": ..., "url": ..., "snippet": ...}]
        """
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            html = self.fetch_url(search_url, timeout=15)
        except ToolExecutionError:
            # Fallback: return empty results on search failure
            return []

        if not BeautifulSoup:
            return [{"title": "Error", "url": "", "snippet": "beautifulsoup4 not installed"}]

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for result in soup.select(".result"):
            title_el = result.select_one(".result__a")
            snippet_el = result.select_one(".result__snippet")
            url_el = result.select_one(".result__url")

            if title_el:
                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # DuckDuckGo wraps URLs in redirects — extract the real URL
                if "uddg=" in url:
                    try:
                        from urllib.parse import parse_qs, urlparse as up
                        real_url = parse_qs(up(url).query).get("uddg", [url])[0]
                        url = real_url
                    except Exception:
                        pass

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })

            if len(results) >= num_results:
                break

        return results

    def summarize_page(self, url, provider="groq"):
        """
        Fetch a URL, extract text, truncate to reasonable size for LLM.

        Returns:
            Extracted text (truncated to ~4000 chars for prompt injection)
        """
        try:
            html = self.fetch_url(url)
            text = self.extract_text(html)
            # Truncate to fit in LLM context with room for other prompts
            return text[:4000] if len(text) > 4000 else text
        except ToolExecutionError as e:
            return f"Error accessing {url}: {str(e)}"
