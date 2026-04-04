"""Lirox v2.0 — Agent Executor

Wraps the browser tool for task execution.
The Executor is responsible for running individual plan steps that require
browser access, and exposes metadata such as `headless_available`.
"""

from lirox.tools.browser import BrowserTool


class Executor:
    """
    Lightweight step executor that wraps the browser tool.

    Attributes
    ----------
    browser : BrowserTool
        The HTTP-based browser tool used for web fetching and search.
    headless_available : bool
        Whether headless browser (CDP) support is configured.
        Falls back gracefully to HTTP-only mode when False.
    """

    def __init__(self):
        self.browser = BrowserTool()
        # Check if a CDP endpoint is reachable for headless browser support
        self.headless_available = self._check_headless()

    # ── Public API ────────────────────────────────────────────────────────────

    def run_step(self, step: dict) -> dict:
        """
        Execute a single plan step and return a result dict.

        Result structure::

            {"status": "success"|"failed", "output": "...", "error": "..."}
        """
        tool = (step.get("tools") or ["llm"])[0]
        task = step.get("task", "")

        try:
            if tool == "browser":
                output = self.browser.fetch_url(task) if task.startswith("http") else self.browser.search_web(task)
                if isinstance(output, list):
                    output = "\n".join(str(r) for r in output)
                return {"status": "success", "output": output, "error": ""}
        except Exception as exc:
            return {"status": "failed", "output": "", "error": str(exc)}

        # Default: return the task description as a placeholder
        return {"status": "success", "output": f"Completed: {task}", "error": ""}

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _check_headless(self) -> bool:
        """Return True when the configured CDP endpoint responds."""
        import os
        import requests
        endpoint = os.getenv("CDP_ENDPOINT", "http://localhost:9222")
        try:
            r = requests.get(f"{endpoint}/json/version", timeout=1)
            return r.status_code == 200
        except Exception:
            return False
