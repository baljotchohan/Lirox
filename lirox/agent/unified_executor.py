"""
Lirox — Unified Execution Bridge (Vision 1)

Routes user queries to the correct execution mode (CHAT / RESEARCH /
BROWSER / HYBRID) based on a :class:`~lirox.utils.smart_router.RoutingDecision`
and chains research → browser verification for HYBRID mode.

Typical usage (called from main.py)::

    from lirox.agent.unified_executor import UnifiedExecutor

    ue = UnifiedExecutor(agent)
    response = ue.run("Current Bitcoin price")
    ue.formatter.render_to_console(response, console)
"""

import logging
import time
from typing import Optional

from lirox.utils.smart_router import SmartRouter, RoutingDecision
from lirox.utils.data_enrichment import DataEnrichment
from lirox.utils.response_formatter import ResponseFormatter, FormattedResponse

logger = logging.getLogger("lirox.unified_executor")


class UnifiedExecutor:
    """
    Unified execution bridge that selects the best mode for each query and
    handles graceful fallbacks.

    Parameters
    ----------
    agent:
        The main :class:`~lirox.agent.core.LiroxAgent` instance (provides
        access to ``executor``, ``memory``, ``profile``, etc.).
    provider:
        LLM provider string (``"auto"`` lets the system choose).
    """

    def __init__(self, agent, provider: str = "auto"):
        self.agent = agent
        self.provider = provider
        self.router = SmartRouter()
        self.formatter = ResponseFormatter()

        # Re-use the browser instances already created by the executor
        _browser = getattr(agent.executor, "browser", None)
        _headless = getattr(agent.executor, "headless_browser", None)

        self.enrichment = DataEnrichment(
            browser_tool=_browser,
            headless_browser=_headless,
        )

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, query: str, verbose: bool = False) -> FormattedResponse:
        """
        Classify *query*, execute the appropriate mode and return a
        :class:`~lirox.utils.response_formatter.FormattedResponse`.
        """
        decision = self.router.route(query)

        if verbose:
            logger.info(
                "Routing: mode=%s confidence=%.2f reason=%s",
                decision.mode,
                decision.confidence,
                decision.reasoning,
            )

        start = time.time()
        try:
            if decision.mode == "CHAT":
                response = self._run_chat(query, decision)
            elif decision.mode == "RESEARCH":
                response = self._run_research(query, decision)
            elif decision.mode == "BROWSER":
                response = self._run_browser(query, decision)
            else:  # HYBRID
                response = self._run_hybrid(query, decision)
        except Exception as exc:
            logger.error("UnifiedExecutor.run failed (mode=%s): %s", decision.mode, exc)
            response = self._fallback_chat(query, str(exc))

        response.elapsed_sec = time.time() - start

        # Learn from execution (persists the routing choice)
        self.router.learn(query, response.mode)
        return response

    # ── Mode handlers ─────────────────────────────────────────────────────────

    def _run_chat(self, query: str, decision: RoutingDecision) -> FormattedResponse:
        """Direct LLM response — no external tools."""
        start = time.time()
        system_prompt = self.agent.profile.to_advanced_system_prompt()
        from lirox.utils.llm import generate_response
        text = generate_response(query, self.provider, system_prompt=system_prompt)
        return self.formatter.from_chat(text, elapsed_sec=time.time() - start)

    def _run_research(self, query: str, decision: RoutingDecision) -> FormattedResponse:
        """Multi-source API research with optional enrichment."""
        from lirox.agent.researcher import Researcher

        start = time.time()
        researcher = Researcher(
            self.agent.executor.browser,
            provider=self.provider,
        )
        report = researcher.research(query, depth="standard")

        # Enrich thin sources
        report.sources = self.enrichment.enrich(report.sources)

        return self.formatter.from_research(report, elapsed_sec=time.time() - start)

    def _run_browser(self, query: str, decision: RoutingDecision) -> FormattedResponse:
        """
        Direct headless-browser fetch.

        If a URL was detected in the query, fetch it directly.  Otherwise
        fall back to a research-based approach.
        """
        start = time.time()
        url = decision.target_url

        # Try headless browser
        headless = getattr(self.agent.executor, "headless_browser", None)
        if headless and getattr(headless, "_browser_available", False) and url:
            try:
                result = headless.fetch_page(url, extract="all", timeout=20)
                return self.formatter.from_browser(
                    result, query, url=url, elapsed_sec=time.time() - start
                )
            except Exception as exc:
                logger.warning("Headless fetch failed, falling back: %s", exc)

        # Fallback: requests-based fetch
        if url:
            try:
                content = self.agent.executor.browser.summarize_page(url)
                fake_result = {
                    "status": "success",
                    "data": {"markdown": content},
                    "metadata": {"title": url, "method": "requests"},
                }
                return self.formatter.from_browser(
                    fake_result, query, url=url, elapsed_sec=time.time() - start
                )
            except Exception as exc:
                logger.warning("Requests browser fetch failed: %s", exc)

        # No URL — fall back to research
        logger.info("No URL for BROWSER mode — falling back to RESEARCH")
        return self._run_research(query, decision)

    def _run_hybrid(self, query: str, decision: RoutingDecision) -> FormattedResponse:
        """
        Research + browser verification.

        Steps:
        1. Run multi-source research.
        2. Enrich thin sources.
        3. Identify the top source URL for real-time verification.
        4. Verify the primary finding via browser fetch.
        5. Merge and return.
        """
        from lirox.agent.researcher import Researcher

        start = time.time()
        researcher = Researcher(
            self.agent.executor.browser,
            provider=self.provider,
        )
        report = researcher.research(query, depth="standard")
        report.sources = self.enrichment.enrich(report.sources)

        # Pick the best source URL for verification
        verify_url = decision.target_url
        if not verify_url and report.sources:
            best = max(report.sources, key=lambda s: s.score)
            verify_url = best.url

        verification: dict = {}
        if verify_url:
            # Use researcher's built-in browser method when headless is available
            try:
                browser_source = researcher.research_with_browser(verify_url)
                if browser_source.content:
                    # Quick claim extraction: take the first finding
                    claim = ""
                    if report.findings:
                        claim = report.findings[0].get("claim", "")
                    verification = self.enrichment.validate_realtime(
                        claim or query, verify_url
                    )
            except Exception as exc:
                logger.warning("Browser verification step failed: %s", exc)
                verification = {
                    "verified": False,
                    "confidence": 0.0,
                    "excerpt": "",
                    "fetched_at": "",
                    "error": str(exc),
                }

        return self.formatter.from_hybrid(
            report, verification, elapsed_sec=time.time() - start
        )

    def _fallback_chat(self, query: str, error_hint: str = "") -> FormattedResponse:
        """Emergency fallback — plain LLM response when everything else fails."""
        try:
            from lirox.utils.llm import generate_response
            system = self.agent.profile.to_advanced_system_prompt()
            text = generate_response(query, self.provider, system_prompt=system)
        except Exception:
            text = (
                "I encountered an issue processing your request. "
                "Please try again or use /research for deep queries."
            )
        return self.formatter.from_chat(text)
