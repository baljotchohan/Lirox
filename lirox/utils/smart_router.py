"""
Lirox — Smart Intent Router (Vision 1)

Classifies user intent into four execution modes using semantic matching
and keyword detection, then returns a routing decision with a confidence
score.

Modes
-----
CHAT     – Direct LLM response, no tool invocation needed.
RESEARCH – Multi-source API research (Tavily / Serper / Exa / DDG).
BROWSER  – Direct headless-browser page scraping / extraction.
HYBRID   – Research + browser verification (real-time or critical data).
"""

import re
import os
import json
from typing import Tuple, List
from lirox.config import PROJECT_ROOT


# ── Routing decision ─────────────────────────────────────────────────────────

class RoutingDecision:
    """Immutable result returned by SmartRouter.route()."""

    __slots__ = ("mode", "confidence", "query", "target_url", "reasoning")

    def __init__(
        self,
        mode: str,
        confidence: float,
        query: str,
        target_url: str = "",
        reasoning: str = "",
    ):
        self.mode = mode                  # CHAT | RESEARCH | BROWSER | HYBRID
        self.confidence = confidence      # 0.0 – 1.0
        self.query = query
        self.target_url = target_url      # non-empty when a URL is detected
        self.reasoning = reasoning        # short human-readable reason

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"RoutingDecision(mode={self.mode!r}, confidence={self.confidence:.2f}, "
            f"query={self.query[:40]!r})"
        )


# ── Pattern banks ─────────────────────────────────────────────────────────────

# Signals that the user wants live / real-time data → HYBRID
_REALTIME_KEYWORDS: List[str] = [
    "current", "live", "right now", "today", "now",
    "price", "stock", "crypto", "bitcoin", "ethereum", "forex",
    "weather", "score", "standings", "breaking news", "trending",
    "real-time", "realtime", "up to date", "as of today",
]

# Realtime keywords that strongly indicate live data (multiple hits → HYBRID)
_STRONG_REALTIME: List[str] = [
    "price", "stock", "crypto", "bitcoin", "ethereum", "forex",
    "weather", "score", "standings", "breaking news", "live",
    "right now", "real-time", "realtime",
]

# Signals direct page scraping / browser automation → BROWSER
_BROWSER_PATTERNS: List[str] = [
    r"scrape\s+", r"extract\s+from\s+(page|site|url|https?://)",
    r"fetch\s+(page|url|site|https?://)", r"go\s+to\s+https?://",
    r"open\s+https?://", r"visit\s+https?://", r"browse\s+to\s+",
    r"fill\s+form", r"automate\s+", r"headless\s+", r"render\s+page",
    r"dynamic\s+content", r"javascript\s+rendered", r"login\s+to\s+",
    r"monitor\s+(page|site|url)", r"watch\s+for\s+changes",
]

# Signals multi-source research → RESEARCH
_RESEARCH_PATTERNS: List[str] = [
    r"research\s+", r"investigate\s+", r"find\s+(info|sources|articles|data)",
    r"look\s+up\s+", r"analyze\s+", r"study\s+", r"explore\s+",
    r"how\s+(does|do|did)\s+", r"why\s+(is|are|does|do)\s+",
    r"explain\s+", r"summarize\s+",
    r"overview\s+(of|on)\s+", r"history\s+of\s+", r"compare\s+",
    r"difference\s+between\s+", r"best\s+(way|practices|tools)",
    r"search\s+for\s+", r"tell\s+me\s+about\s+",
]

# Signals simple conversational reply → CHAT
_CHAT_PATTERNS: List[str] = [
    r"^(hi|hello|hey|yo|sup)\b",
    r"how\s+are\s+you", r"what\s+do\s+you\s+(think|feel|know)",
    r"can\s+you\s+help\s+me\s+(with\s+)?(a\s+)?question",
    r"just\s+wondering", r"quick\s+question", r"remind\s+me",
    r"thank(s| you)", r"that('?s| is)\s+(great|awesome|cool|nice)",
    r"do\s+you\s+(know|remember|have)",
    r"what\s+time\s+is\s+it", r"who\s+are\s+you",
]

# Regex to detect a bare URL in the query
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

# Scaling multiplier: a single pattern match out of many is amplified so
# sparse-but-clear signals (1 hit in 16 patterns) still cross routing thresholds.
_PATTERN_SCORE_MULTIPLIER = 2.0

# Confidence weights for URL-based BROWSER routing
_BASE_URL_CONFIDENCE = 0.7
_BROWSER_SCORE_WEIGHT = 0.3


def _score(text: str, patterns: List[str]) -> float:
    """Return fraction of patterns that match *text*, scaled by _PATTERN_SCORE_MULTIPLIER."""
    if not patterns:
        return 0.0
    hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
    return min(hits / len(patterns) * _PATTERN_SCORE_MULTIPLIER, 1.0)


def _has_realtime_signal(text: str) -> bool:
    return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in _REALTIME_KEYWORDS)


def _has_strong_realtime(text: str) -> bool:
    """True when at least one 'strong' real-time keyword appears (live data)."""
    return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in _STRONG_REALTIME)


def _extract_url(text: str) -> str:
    match = _URL_RE.search(text)
    return match.group(0) if match else ""


# ── Smart Router ──────────────────────────────────────────────────────────────

class SmartRouter:
    """
    Routes user queries to the optimal execution mode.

    Usage::

        from lirox.utils.smart_router import SmartRouter
        sr = SmartRouter()
        decision = sr.route("Current Bitcoin price")
        # decision.mode == "HYBRID"
    """

    _STORAGE_FILE = os.path.join(PROJECT_ROOT, "smart_router_history.json")

    def __init__(self):
        self._history: List[dict] = []
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def route(self, user_input: str) -> RoutingDecision:
        """
        Classify *user_input* and return a :class:`RoutingDecision`.

        The decision logic (in priority order):

        1. Bare URL detected → BROWSER (direct scrape)
        2. Browser keyword patterns → BROWSER
        3. Explicit research verb + real-time → RESEARCH (research intent wins)
        4. Real-time signal + research patterns → HYBRID
        5. Real-time signal alone → HYBRID (research + verify)
        6. Research patterns → RESEARCH
        7. Short / conversational → CHAT
        8. Fallback → CHAT
        """
        text = user_input.strip()
        lower = text.lower()

        url = _extract_url(text)
        browser_score = _score(lower, _BROWSER_PATTERNS)
        research_score = _score(lower, _RESEARCH_PATTERNS)
        chat_score = _score(lower, _CHAT_PATTERNS)
        realtime = _has_realtime_signal(lower)
        strong_realtime = _has_strong_realtime(lower)
        # ── Explicit research verb detection ─────────────────────────────────
        # "What is X?" on its own is conversational; treat as explicit research
        # only when the query is substantive (> 5 words) or uses specific verbs.
        _STRONG_RESEARCH_VERBS = re.compile(
            r"\b(research|investigate|analyze|analyse|study|summarize|"
            r"overview|compare|history\s+of|difference\s+between|"
            r"explain\s+(?:how|why|what)|how\s+(does|do|did))\b",
            re.IGNORECASE,
        )
        _WEAK_RESEARCH_VERBS = re.compile(
            r"\b(what\s+(is|are|was|were)|tell\s+me\s+about)\b",
            re.IGNORECASE,
        )
        # Strong verbs always count; weak verbs only count for longer queries
        explicit_research = bool(_STRONG_RESEARCH_VERBS.search(lower)) or (
            bool(_WEAK_RESEARCH_VERBS.search(lower)) and len(text.split()) > 5
        )

        # 1. Bare URL → BROWSER (always wins when URL is present)
        if url:
            return RoutingDecision(
                mode="BROWSER",
                confidence=min(_BASE_URL_CONFIDENCE + browser_score * _BROWSER_SCORE_WEIGHT, 1.0),
                query=text,
                target_url=url,
                reasoning="Direct URL detected — routing to headless browser.",
            )

        # 2. Strong browser signals → BROWSER
        if browser_score > 0.25:
            return RoutingDecision(
                mode="BROWSER",
                confidence=min(0.6 + browser_score * 0.4, 1.0),
                query=text,
                target_url=url,
                reasoning="Browser/scraping keywords detected.",
            )

        # 3. Explicit research verb overrides soft real-time → RESEARCH
        #    BUT if a strong real-time keyword is present (price, live, etc.)
        #    the user wants current data → HYBRID takes priority.
        #    Weak verbs (what is/are/were) only trigger research for longer queries.
        if explicit_research and not strong_realtime:
            # Strong verbs: always route to RESEARCH if research_score is detectable
            # Weak verbs: route to RESEARCH for longer queries even with 0 research_score
            _str_match = bool(_STRONG_RESEARCH_VERBS.search(lower))
            if _str_match and research_score > 0.05:
                return RoutingDecision(
                    mode="RESEARCH",
                    confidence=min(0.6 + research_score * 0.4, 1.0),
                    query=text,
                    reasoning="Explicit research intent detected.",
                )
            if not _str_match and len(text.split()) > 5:
                # Weak verb ("what were/is/are") on a substantive query.
                # If realtime signal is present, promote to HYBRID instead.
                if realtime:
                    return RoutingDecision(
                        mode="HYBRID",
                        confidence=0.75,
                        query=text,
                        reasoning="Factual question with real-time data need — hybrid mode.",
                    )
                # Factual/historical question → RESEARCH
                return RoutingDecision(
                    mode="RESEARCH",
                    confidence=0.65,
                    query=text,
                    reasoning="Factual question detected — routing to research.",
                )

        # 4. Real-time + research patterns → HYBRID
        if realtime and research_score > 0.1:
            return RoutingDecision(
                mode="HYBRID",
                confidence=0.85,
                query=text,
                target_url=url,
                reasoning="Real-time data need with research context — using hybrid mode.",
            )

        # 5. Real-time alone → HYBRID
        if realtime:
            return RoutingDecision(
                mode="HYBRID",
                confidence=0.75,
                query=text,
                target_url=url,
                reasoning="Real-time signal detected — research + browser verification.",
            )

        # 6. Research patterns → RESEARCH
        if research_score > 0.1:
            return RoutingDecision(
                mode="RESEARCH",
                confidence=min(0.55 + research_score * 0.45, 1.0),
                query=text,
                reasoning="Research/information-seeking intent detected.",
            )

        # 7. Chat signals or very short query → CHAT
        if chat_score > 0.2 or len(text.split()) <= 4:
            return RoutingDecision(
                mode="CHAT",
                confidence=max(0.55, chat_score),
                query=text,
                reasoning="Conversational intent detected — direct LLM response.",
            )

        # 8. Default: CHAT
        return RoutingDecision(
            mode="CHAT",
            confidence=0.5,
            query=text,
            reasoning="No strong signal — defaulting to direct response.",
        )

    def learn(self, query: str, chosen_mode: str) -> None:
        """Persist a user-confirmed routing choice for future reference."""
        entry = {"query": query[:120], "mode": chosen_mode}
        self._history.append(entry)
        self._save()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(self._STORAGE_FILE):
            try:
                with open(self._STORAGE_FILE, "r") as fh:
                    self._history = json.load(fh)
            except Exception:
                self._history = []

    def _save(self) -> None:
        try:
            with open(self._STORAGE_FILE, "w") as fh:
                json.dump(self._history[-500:], fh, indent=2)
        except Exception:
            pass


# ── Module-level singleton ────────────────────────────────────────────────────

smart_router = SmartRouter()
