"""
Lirox — Data Enrichment Layer (Vision 1)

Enriches research results by fetching the full page content for sources
that only have short snippets, validates information across sources, and
handles time-sensitive data that needs browser-based verification.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger("lirox.data_enrichment")

# Maximum characters of content to store per enriched source
MAX_ENRICHED_CONTENT_LENGTH = 5000


class DataEnrichment:
    """
    Enriches a list of :class:`~lirox.agent.researcher.ResearchSource` objects
    by pulling full-page content via the headless browser or the requests-based
    fallback browser tool.

    Parameters
    ----------
    browser_tool:
        Instance of ``BrowserTool`` (requests-based, always available).
    headless_browser:
        Instance of ``HeadlessBrowserTool`` (optional; ``None`` when
        Lightpanda is not installed).
    max_workers:
        Thread-pool size for parallel enrichment.
    min_content_length:
        Sources with ``content`` already longer than this are skipped.
    """

    def __init__(
        self,
        browser_tool,
        headless_browser=None,
        max_workers: int = 4,
        min_content_length: int = 400,
    ):
        self.browser = browser_tool
        self.headless = headless_browser
        self.max_workers = max_workers
        self.min_content_length = min_content_length

    # ── Public API ────────────────────────────────────────────────────────────

    def enrich(self, sources: list) -> list:
        """
        Return a new list of sources where thin snippets have been replaced
        with full page content.  Sources that already have sufficient content
        are returned unchanged.
        """
        needs_enrichment = [
            s for s in sources
            if not s.content or len(s.content) < self.min_content_length
        ]
        already_rich = [
            s for s in sources
            if s.content and len(s.content) >= self.min_content_length
        ]

        if not needs_enrichment:
            return sources

        logger.info(
            "Enriching %d/%d sources (others already have content)",
            len(needs_enrichment),
            len(sources),
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._enrich_one, src): src for src in needs_enrichment}
            enriched = []
            for future in as_completed(futures):
                try:
                    enriched.append(future.result())
                except Exception as exc:
                    src = futures[future]
                    logger.warning("Enrichment failed for %s: %s", src.url, exc)
                    enriched.append(src)  # keep original

        return already_rich + enriched

    def validate_realtime(self, claim: str, url: str) -> dict:
        """
        Attempt to verify a real-time claim by fetching *url* and checking
        whether the claim appears in the extracted content.

        Returns a dict::

            {
                "verified": bool,
                "confidence": float,   # 0.0 – 1.0
                "excerpt":   str,      # relevant snippet from page
                "fetched_at": str,     # ISO timestamp
            }
        """
        content = self._fetch_content(url, prefer_headless=True)
        if not content:
            return {
                "verified": False,
                "confidence": 0.0,
                "excerpt": "",
                "fetched_at": datetime.now().isoformat(),
            }

        # Simple substring heuristic — a real implementation would use the LLM
        claim_words = set(claim.lower().split())
        content_lower = content.lower()
        matched = sum(1 for w in claim_words if w in content_lower)
        coverage = matched / max(len(claim_words), 1)

        # Find a short relevant excerpt around the first matched word
        excerpt = ""
        for word in claim_words:
            pos = content_lower.find(word)
            if pos >= 0:
                start = max(0, pos - 80)
                end = min(len(content), pos + 160)
                excerpt = content[start:end].strip()
                break

        return {
            "verified": coverage > 0.5,
            "confidence": round(min(coverage * 1.2, 1.0), 2),
            "excerpt": excerpt,
            "fetched_at": datetime.now().isoformat(),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _enrich_one(self, source) -> object:
        """Fetch and attach content to a single ResearchSource."""
        content = self._fetch_content(source.url, prefer_headless=False)
        if content:
            source.content = content[:MAX_ENRICHED_CONTENT_LENGTH]
        return source

    def _fetch_content(self, url: str, prefer_headless: bool = False) -> Optional[str]:
        """
        Fetch page content for *url*.  Tries headless browser first when
        *prefer_headless* is True and Lightpanda is available; falls back
        to the requests-based browser tool.
        """
        if prefer_headless and self.headless:
            try:
                _avail = getattr(self.headless, "_browser_available", False)
                if _avail:
                    result = self.headless.fetch_page(url, extract="markdown", timeout=15)
                    if result.get("status") == "success":
                        md = result.get("data", {}).get("markdown", "")
                        if md and len(md) > 100:
                            return md
            except Exception as exc:
                logger.debug("Headless fetch failed for %s: %s", url, exc)

        # Fallback: requests-based browser tool
        try:
            return self.browser.summarize_page(url)
        except Exception as exc:
            logger.warning("Requests fetch failed for %s: %s", url, exc)
            return None
