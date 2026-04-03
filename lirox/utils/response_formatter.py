"""
Lirox — Response Formatter (Vision 1)

Structures the final response that is shown to the user regardless of which
execution mode was used (CHAT / RESEARCH / BROWSER / HYBRID).

Output schema
-------------
{
    "answer":       str,          # primary response text
    "key_insights": List[str],    # bullet-point takeaways (optional)
    "sources":      List[dict],   # [{title, url, domain, confidence}]
    "verification": dict,         # {verified, confidence, excerpt, fetched_at}
    "mode":         str,          # CHAT | RESEARCH | BROWSER | HYBRID
    "timestamp":    str,          # ISO timestamp of generation
    "elapsed_sec":  float,        # wall-clock time taken
    "api_calls":    int,          # number of external API calls made
}
"""

from datetime import datetime
from typing import List, Optional

# Maximum characters of browser-fetched content to include in a response
MAX_BROWSER_CONTENT_LENGTH = 6000


class FormattedResponse:
    """Structured response returned by :class:`ResponseFormatter`."""

    __slots__ = (
        "answer",
        "key_insights",
        "sources",
        "verification",
        "mode",
        "timestamp",
        "elapsed_sec",
        "api_calls",
    )

    def __init__(
        self,
        answer: str,
        mode: str,
        key_insights: Optional[List[str]] = None,
        sources: Optional[List[dict]] = None,
        verification: Optional[dict] = None,
        elapsed_sec: float = 0.0,
        api_calls: int = 0,
    ):
        self.answer = answer
        self.mode = mode
        self.key_insights: List[str] = key_insights or []
        self.sources: List[dict] = sources or []
        self.verification: dict = verification or {}
        self.timestamp = datetime.now().isoformat()
        self.elapsed_sec = elapsed_sec
        self.api_calls = api_calls

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "key_insights": self.key_insights,
            "sources": self.sources,
            "verification": self.verification,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "elapsed_sec": round(self.elapsed_sec, 2),
            "api_calls": self.api_calls,
        }


class ResponseFormatter:
    """
    Converts raw outputs from different execution modes into a consistent
    :class:`FormattedResponse`.

    Usage::

        fmt = ResponseFormatter()
        response = fmt.from_research(report, elapsed_sec=3.5)
        response = fmt.from_browser(fetch_result, query, elapsed_sec=1.2)
        response = fmt.from_chat(llm_text)
        response = fmt.from_hybrid(report, verification, elapsed_sec=5.0)
    """

    # ── Factory helpers ───────────────────────────────────────────────────────

    def from_chat(self, text: str, elapsed_sec: float = 0.0) -> FormattedResponse:
        """Wrap a plain LLM reply."""
        return FormattedResponse(
            answer=text,
            mode="CHAT",
            elapsed_sec=elapsed_sec,
            api_calls=1,
        )

    def from_research(self, report, elapsed_sec: float = 0.0) -> FormattedResponse:
        """
        Build a :class:`FormattedResponse` from a
        :class:`~lirox.agent.researcher.ResearchReport`.
        """
        sources = [
            {
                "title": s.title,
                "url": s.url,
                "domain": s.domain,
                "confidence": round(s.score, 2),
                "citation_id": s.citation_id,
            }
            for s in report.sources
        ]

        insights = [
            f.get("claim", "")
            for f in (report.findings or [])
            if f.get("claim")
        ][:8]

        return FormattedResponse(
            answer=report.summary,
            mode="RESEARCH",
            key_insights=insights,
            sources=sources,
            elapsed_sec=elapsed_sec,
            api_calls=len(report.search_apis_used or []),
        )

    def from_browser(
        self,
        fetch_result: dict,
        query: str,
        url: str = "",
        elapsed_sec: float = 0.0,
    ) -> FormattedResponse:
        """
        Build a :class:`FormattedResponse` from a headless-browser fetch result
        (the dict returned by ``HeadlessBrowserTool.fetch_page``).
        """
        data = fetch_result.get("data", {})
        content = data.get("markdown", "") or data.get("text", "")
        meta = fetch_result.get("metadata", {})

        source = {
            "title": meta.get("title", url),
            "url": url or meta.get("url", ""),
            "domain": _domain(url),
            "confidence": 0.9 if fetch_result.get("status") == "success" else 0.3,
        }

        return FormattedResponse(
            answer=content[:MAX_BROWSER_CONTENT_LENGTH] if content else "No content extracted.",
            mode="BROWSER",
            sources=[source] if source["url"] else [],
            elapsed_sec=elapsed_sec,
            api_calls=0,
        )

    def from_hybrid(
        self,
        report,
        verification: dict,
        elapsed_sec: float = 0.0,
    ) -> FormattedResponse:
        """
        Build a :class:`FormattedResponse` combining research and browser
        verification results.
        """
        base = self.from_research(report, elapsed_sec=elapsed_sec)
        base.mode = "HYBRID"
        base.verification = verification
        base.api_calls += 1  # count the verification fetch
        return base

    # ── Rich terminal rendering ───────────────────────────────────────────────

    def render_to_console(self, response: FormattedResponse, console=None) -> None:
        """
        Pretty-print *response* to the Rich console.  Falls back to plain
        ``print`` when *console* is ``None``.
        """
        try:
            from rich.console import Console as RichConsole
            from rich.markdown import Markdown
            from rich.table import Table
            from lirox.ui.display import CLR_ACCENT, CLR_WARN
        except ImportError:
            print(response.answer)
            return

        con = console or RichConsole()

        # Mode badge
        _mode_colour = {
            "CHAT": "cyan",
            "RESEARCH": "green",
            "BROWSER": "blue",
            "HYBRID": "magenta",
        }
        colour = _mode_colour.get(response.mode, "white")
        con.print(
            f"\n[bold {colour}]▸ {response.mode} MODE[/]  "
            f"[dim]{response.elapsed_sec:.1f}s[/]\n"
        )

        # Main answer
        try:
            con.print(Markdown(response.answer))
        except Exception:
            con.print(f"[{CLR_ACCENT}]{response.answer}[/]")

        # Key insights
        if response.key_insights:
            con.print(f"\n[bold {colour}]Key Insights[/]")
            for insight in response.key_insights[:6]:
                if insight.strip():
                    con.print(f"  • {insight}")

        # Sources table
        if response.sources:
            table = Table(title="Sources", border_style="dim", show_header=True)
            table.add_column("#", width=3)
            table.add_column("Title", style="white")
            table.add_column("Domain")
            table.add_column("Confidence", justify="right")
            for i, s in enumerate(response.sources[:8], 1):
                bar = "█" * int(s["confidence"] * 5)
                table.add_row(
                    str(i),
                    str(s.get("title", ""))[:45],
                    str(s.get("domain", "")),
                    f"{bar} {int(s['confidence'] * 100)}%",
                )
            con.print()
            con.print(table)

        # Verification status
        if response.verification:
            verified = response.verification.get("verified", False)
            vconf = response.verification.get("confidence", 0.0)
            icon = "✅" if verified else "⚠️"
            status = "Verified" if verified else "Unverified"
            con.print(
                f"\n[dim]{icon} Browser Verification: {status} "
                f"({int(vconf * 100)}% confidence) — "
                f"{response.verification.get('fetched_at', '')}[/]"
            )

        con.print()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


# ── Module-level singleton ────────────────────────────────────────────────────

response_formatter = ResponseFormatter()
