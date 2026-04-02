"""
Lirox v0.7.1 — Headless Browser Tool

High-level browser API registered with the Lirox executor.
Provides fetch_page, interact_with_page, extract_structured_data,
and monitor_for_changes methods.

Falls back to existing requests-based BrowserTool when Lightpanda is unavailable.
Includes strict timeout guards to prevent hanging on broken connections.
"""

import logging
import time
from typing import Optional, List, Dict, Any

logger = logging.getLogger("lirox.browser.tool")

# Lazy import guards — never crash on missing deps
_session_manager = None
_headless_available = None  # tri-state: None = unknown, True/False = tested


def _check_headless() -> bool:
    """One-time check if headless browser subsystem is functional."""
    global _headless_available
    if _headless_available is not None:
        return _headless_available

    try:
        from lirox.tools.browser_manager import BrowserSessionManager
        from lirox.tools.browser_security import BrowserSecurityValidator
        from lirox.config import BROWSER_CONFIG

        mgr = BrowserSessionManager(
            max_instances=BROWSER_CONFIG.get("max_instances", 5),
            browser_path=BROWSER_CONFIG.get("lightpanda_path", "./lightpanda"),
            port=BROWSER_CONFIG.get("port", 9222),
            timeout=BROWSER_CONFIG.get("timeout", 30),
        )
        _headless_available = mgr.is_available
        if _headless_available:
            logger.info("Headless browser (Lightpanda) is available")
        else:
            logger.info("Headless browser not available — using requests fallback")
        return _headless_available
    except Exception as e:
        logger.info(f"Headless browser check failed: {e}")
        _headless_available = False
        return False


def _get_manager():
    """Get or create the global session manager (only if headless is available)."""
    global _session_manager
    if not _check_headless():
        return None
    if _session_manager is None:
        from lirox.tools.browser_manager import BrowserSessionManager
        from lirox.config import BROWSER_CONFIG
        _session_manager = BrowserSessionManager(
            max_instances=BROWSER_CONFIG.get("max_instances", 5),
            browser_path=BROWSER_CONFIG.get("lightpanda_path", "./lightpanda"),
            port=BROWSER_CONFIG.get("port", 9222),
            timeout=BROWSER_CONFIG.get("timeout", 30),
        )
    return _session_manager


def get_browser_status() -> Dict[str, Any]:
    """Get the browser subsystem status for diagnostics."""
    mgr = _get_manager()
    if mgr:
        return mgr.get_status()
    return {
        "binary_available": False,
        "method": "requests",
        "note": "Using portable requests-based browser (works everywhere)",
    }


class HeadlessBrowserTool:
    """
    High-level browser tool for Lirox executor integration.

    Methods are synchronous (wrapping async CDP internally when headless is available).
    Always falls back to robust requests-based BrowserTool — never hangs or crashes.
    """

    def __init__(self):
        self._fallback = None
        self._security = None
        self._data_validator = None
        self._headless_tested = False
        self._headless_works = False

        # Lazy security init
        try:
            from lirox.tools.browser_security import BrowserSecurityValidator, DataValidator
            self._security = BrowserSecurityValidator()
            self._data_validator = DataValidator()
        except ImportError:
            pass

    @property
    def _browser_available(self) -> bool:
        """Check if headless browser is available AND working."""
        mgr = _get_manager()
        return mgr is not None and mgr.is_available

    def _get_fallback(self):
        """Get the traditional requests-based browser tool as fallback."""
        if self._fallback is None:
            from lirox.tools.browser import BrowserTool
            self._fallback = BrowserTool()
        return self._fallback

    # ─── Core Methods ─────────────────────────────────────────────────────────

    def fetch_page(self, url: str, extract: str = "markdown",
                   timeout: int = 30, use_headless: bool = True) -> Dict[str, Any]:
        """
        Fetch a web page and extract content.

        Args:
            url: URL to fetch
            extract: "markdown" | "html" | "links" | "tables" | "all"
            timeout: Navigation timeout in seconds
            use_headless: Try headless browser first (fallback to requests)

        Returns:
            {
                "status": "success",
                "url": str,
                "data": {...},
                "metadata": {"title": str, "method": str, "duration": float}
            }
        """
        # Validate URL if security is available
        if self._security:
            is_safe, reason = self._security.validate_url(url)
            if not is_safe:
                return {"status": "error", "error": f"URL rejected: {reason}"}

        start = time.time()

        # Try headless browser first (with aggressive timeout to prevent hanging)
        if use_headless and self._browser_available:
            result = self._fetch_with_headless(url, extract, timeout)
            if result:
                result["metadata"]["duration"] = round(time.time() - start, 2)
                result["metadata"]["method"] = "headless"
                return result

        # Always fall back to requests-based browser
        result = self._fetch_with_requests(url, extract)
        result["metadata"]["duration"] = round(time.time() - start, 2)
        result["metadata"]["method"] = "requests"
        return result

    def _fetch_with_headless(self, url: str, extract: str,
                              timeout: int) -> Optional[Dict[str, Any]]:
        """Fetch page using headless Lightpanda browser with strict timeout."""
        manager = _get_manager()
        if not manager:
            return None

        import concurrent.futures

        def _do_headless():
            session = manager.acquire_session()
            if not session:
                return None
            try:
                nav_result = session.navigate(url, timeout=timeout)
                data = {}

                if extract in ("markdown", "all"):
                    data["markdown"] = session.get_markdown()
                if extract in ("html", "all"):
                    data["html"] = session.get_html()
                if extract in ("links", "all"):
                    data["links"] = session.extract_links()
                if extract in ("tables", "all"):
                    data["tables"] = session.extract_tables()

                page_state = session.get_page_state()
                manager.release_session(session)

                return {
                    "status": "success",
                    "url": nav_result.get("url", url),
                    "data": data,
                    "metadata": {
                        "title": page_state.get("title", ""),
                        "element_count": page_state.get("elementCount", 0),
                        "link_count": page_state.get("linkCount", 0),
                    },
                }
            except Exception as e:
                logger.warning(f"Headless fetch failed for {url}: {e}")
                try:
                    session.metrics.error_count += 1
                    manager.release_with_error(session)
                except Exception:
                    pass
                return None

        # Run headless fetch with a hard timeout guard to prevent hanging
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_headless)
                result = future.result(timeout=min(timeout + 5, 35))
                return result
        except concurrent.futures.TimeoutError:
            logger.warning(f"Headless browser timed out for {url}, falling back to requests")
            return None
        except Exception as e:
            logger.warning(f"Headless browser error: {e}")
            return None

    def _fetch_with_requests(self, url: str, extract: str) -> Dict[str, Any]:
        """Fetch page using traditional requests + BeautifulSoup."""
        browser = self._get_fallback()

        try:
            html = browser.fetch_url(url)
            data = {}

            if extract in ("markdown", "all"):
                data["markdown"] = browser.extract_text(html)
            if extract in ("html", "all"):
                data["html"] = html[:50000]  # Cap HTML size
            if extract in ("links", "all"):
                data["links"] = self._extract_links_from_html(html)
            if extract in ("tables", "all"):
                data["tables"] = self._extract_tables_from_html(html)

            return {
                "status": "success",
                "url": url,
                "data": data,
                "metadata": {"title": self._extract_title(html)},
            }

        except Exception as e:
            return {
                "status": "error",
                "url": url,
                "error": str(e),
                "data": {},
                "metadata": {},
            }

    # ─── Interactive Browsing ─────────────────────────────────────────────────

    def interact_with_page(self, url: str, actions: List[Dict[str, Any]],
                            extract_after: bool = True) -> Dict[str, Any]:
        """
        Navigate to URL and execute a sequence of interactions.
        Requires headless browser — returns error if unavailable.
        """
        if not self._browser_available:
            return {
                "status": "error",
                "error": "Headless browser not available. Interactive browsing requires Lightpanda.",
            }

        manager = _get_manager()
        session = manager.acquire_session()
        if not session:
            return {"status": "error", "error": "No browser sessions available"}

        try:
            session.navigate(url)
            action_results = []

            for i, action in enumerate(actions):
                act_type = action.get("action", "")
                result = self._execute_action(session, action)
                action_results.append({
                    "step": i + 1,
                    "action": act_type,
                    "result": result,
                })

            extracted = {}
            if extract_after:
                extracted["markdown"] = session.get_markdown()

            page_state = session.get_page_state()
            manager.release_session(session)

            return {
                "status": "success",
                "final_url": page_state.get("url", url),
                "action_results": action_results,
                "extracted_data": extracted,
                "metadata": {
                    "title": page_state.get("title", ""),
                    "actions_executed": len(actions),
                },
            }

        except Exception as e:
            logger.error(f"Page interaction failed: {e}")
            manager.release_with_error(session)
            return {"status": "error", "error": str(e)}

    def _execute_action(self, session, action: Dict[str, Any]) -> Any:
        """Execute a single browser action."""
        act_type = action.get("action", "").lower()
        selector = action.get("selector", "")

        if act_type == "click":
            return session.click(selector)
        elif act_type == "type":
            return session.type_text(selector, action.get("text", ""))
        elif act_type == "wait":
            timeout = action.get("timeout", 10000)
            return session.wait_for_selector(selector, timeout)
        elif act_type == "extract":
            extract_type = action.get("type", "markdown")
            if extract_type == "markdown":
                return session.get_markdown()
            elif extract_type == "html":
                return session.get_html()
            elif extract_type == "links":
                return session.extract_links()
            elif extract_type == "tables":
                return session.extract_tables()
        elif act_type == "evaluate":
            return session.evaluate_js(action.get("script", ""))
        elif act_type == "screenshot":
            return session.take_screenshot(action.get("path", "screenshot.png"))
        elif act_type == "fill_form":
            return session.fill_form(action.get("fields", {}))
        elif act_type == "submit":
            return session.submit_form(selector)
        else:
            return f"Unknown action: {act_type}"

    # ─── Structured Data Extraction ───────────────────────────────────────────

    def extract_structured_data(self, url: str,
                                 schema: Dict[str, str]) -> Dict[str, Any]:
        """
        Navigate to URL and extract structured data based on CSS selector schema.

        Args:
            url: Target URL
            schema: {"field_name": "css_selector"} mapping

        Returns:
            {"status": "success", "data": {"field": "value", ...}, "url": str}
        """
        # Always try requests-based extraction (works on all devices)
        return self._extract_structured_requests(url, schema)

    def _extract_structured_requests(self, url: str,
                                      schema: Dict[str, str]) -> Dict[str, Any]:
        """Extract structured data using requests + BS4."""
        browser = self._get_fallback()
        try:
            html = browser.fetch_url(url)
            data = {}
            for field_name, selector in schema.items():
                results = browser.extract_data(html, selector)
                data[field_name] = results[0] if results else ""

            return {
                "status": "success",
                "url": url,
                "data": data,
                "method": "requests",
            }
        except Exception as e:
            return {"status": "error", "url": url, "error": str(e), "data": {}}

    # ─── Multi-Page Fetching ──────────────────────────────────────────────────

    def fetch_multiple_pages(self, urls: List[str],
                              extract: str = "markdown",
                              max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs with concurrent execution.

        Args:
            urls: List of URLs to fetch
            extract: Extraction type
            max_concurrent: Max parallel fetches

        Returns:
            List of fetch results
        """
        import concurrent.futures

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            future_to_url = {
                pool.submit(self.fetch_page, url, extract): url for url in urls
            }
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    result = future.result(timeout=35)
                    results.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    results.append({
                        "status": "error",
                        "url": url,
                        "error": str(e),
                        "data": {},
                        "metadata": {},
                    })

        return results

    # ─── Helper Methods ───────────────────────────────────────────────────────

    def _extract_links_from_html(self, html: str) -> List[Dict[str, str]]:
        """Extract links from raw HTML using BS4."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                links.append({
                    "url": a["href"],
                    "text": a.get_text(strip=True),
                    "title": a.get("title", ""),
                })
            return links
        except Exception:
            return []

    def _extract_tables_from_html(self, html: str) -> List[List[Dict]]:
        """Extract tables from raw HTML using BS4."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            tables = []
            for table in soup.find_all("table"):
                rows = []
                headers = [th.get_text(strip=True) for th in table.find_all("th")]
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if cells:
                        row = {}
                        for j, cell in enumerate(cells):
                            key = headers[j] if j < len(headers) else f"col_{j}"
                            row[key] = cell
                        rows.append(row)
                if rows:
                    tables.append(rows)
            return tables
        except Exception:
            return []

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            return title_tag.get_text(strip=True) if title_tag else ""
        except Exception:
            return ""
