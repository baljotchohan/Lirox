"""
Lirox v2.0 — Agent Executor

Combines the browser tool with headless detection to execute
web-based tasks with graceful fallback.
"""

from __future__ import annotations


class Executor:
    """
    Executes tasks using available tools (browser, headless browser, etc.).

    Attributes:
        browser: BrowserTool instance for HTTP fetching.
        headless_available: Whether a headless browser (e.g. Playwright) is available.
    """

    def __init__(self):
        from lirox.tools.browser import BrowserTool
        self.browser = BrowserTool()
        self.headless_available = self._check_headless()

    def _check_headless(self) -> bool:
        """Check if a headless browser runtime is available."""
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            pass
        try:
            import selenium  # noqa: F401
            return True
        except ImportError:
            pass
        return False

    def fetch(self, url: str) -> str:
        """Fetch a URL using the available browser mechanism."""
        return self.browser.fetch_url(url)
