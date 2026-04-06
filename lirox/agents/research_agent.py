"""
Lirox v3.0 — Research Agent
Perplexity-style terminal research:
  - Proactive topic suggestions on session start
  - Combined browser + search for live data (GitHub trending, news, etc.)
  - Multi-source synthesis with source attribution
  - Mode-aware depth control
"""
from __future__ import annotations

import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.config import MAX_LLM_PROMPT_CHARS, ThinkingMode

RESEARCH_SYS = """You are {agent_name}'s Research Agent — a Perplexity-style deep researcher.

MISSION: Find verified, current information. Synthesize. Attribute sources.
FORMAT:
  ## Answer
  [Direct, clear answer]
  
  ## Key Findings
  [Bullet points of key data points with sources]
  
  ## Sources
  [List of sources used]

If search failed, clearly state: "Note: web search unavailable — answering from training data."
"""

RESEARCH_PROACTIVE_SUGGESTIONS = [
    "🔬 What research topic shall we dive into today?",
    "📡 Ready to research. Trending topics: AI developments, market news, tech releases. Or name your topic.",
    "🧪 Research agent ready. What would you like to investigate?",
]

ONBOARDING_MSG = """🔬 **Research Agent — Perplexity in your terminal!**

I search the web, synthesize multiple sources, and give you verified, cited answers.

To make me more powerful:
  • **`TAVILY_API_KEY`** — Premium research-grade search results
  • Without it, I use DuckDuckGo (still works great)

Every research query is unique — I'll dive deep rather than reuse past answers.

**What would you like to research today?**"""


class ResearchAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "research"

    @property
    def description(self) -> str:
        return "Deep multi-source research, web synthesis, cited answers"

    def get_onboarding_message(self) -> str:
        return ONBOARDING_MSG

    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = ThinkingMode.THINK
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time

        logger = get_logger(f"lirox.agents.{self.name}")
        start  = time.time()
        log_with_metadata(logger, "INFO", "Research Agent started", query=query[:100], mode=mode)



        yield {"type": "agent_progress", "message": "Research Agent starting..."}

        # ── Step 1: Live data check (GitHub, news, etc.)
        live_data = ""
        if self._is_live_query(query):
            yield {"type": "tool_call", "message": "Fetching live data..."}
            live_data = self._fetch_live_data(query)
            if live_data:
                yield {"type": "tool_result", "message": f"✅ Live data retrieved ({len(live_data)} chars)"}

        # ── Step 2: Multi-source search
        yield {"type": "tool_call", "message": "Searching multiple sources..."}
        search_results = self._multi_search(query)
        yield {"type": "tool_result", "message": "Search complete"}

        # ── Step 3: Synthesize
        yield {"type": "agent_progress", "message": "Synthesizing findings..."}

        combined = ""
        if live_data:
            combined += f"## Live Data\n{live_data}\n\n"
        combined += search_results

        agent_name = self.profile_data.get("agent_name", "Lirox")
        sys_p      = RESEARCH_SYS.format(agent_name=agent_name)
        if mode == ThinkingMode.FAST:
            sys_p += "\n\nBe brief — 3-5 bullet points max."

        prompt = f"Research Query: {query}\n\n{combined[:MAX_LLM_PROMPT_CHARS]}"
        if context:
            prompt += f"\n\nReasoning context:\n{context}"
        prompt += "\n\nSynthesize comprehensively. Cross-reference sources. Note conflicts."

        if not search_results or "No results" in search_results:
            prompt += "\n\nNOTE: Web search returned no results. Answer from training data and clearly caveat."

        answer = generate_response(prompt, provider="auto", system_prompt=sys_p)
        self.memory.save_exchange(query, answer)

        log_with_metadata(logger, "INFO", "Research Agent completed",
                          duration_ms=int((time.time() - start) * 1000))
        yield {"type": "done", "answer": answer, "sources": []}

    def _is_live_query(self, query: str) -> bool:
        """Detect queries that need live web data."""
        live_indicators = [
            "trending", "today", "latest", "current", "right now", "2025", "2026",
            "github trending", "news", "price of", "stock", "weather",
            "most popular", "top repos", "recent", "this week",
        ]
        q = query.lower()
        return any(k in q for k in live_indicators)

    def _fetch_live_data(self, query: str) -> str:
        """Fetch live data: GitHub trending, news headlines, etc."""
        q = query.lower()

        # GitHub trending
        if "github" in q and ("trending" in q or "popular" in q or "repo" in q):
            try:
                content = self.fetch_url("https://github.com/trending")
                if content and "error" not in content.lower():
                    return f"Source: github.com/trending\n\n{content[:3000]}"
            except Exception:
                pass

        # Hacker News
        if "hacker news" in q or "hn" in q or "hackernews" in q:
            try:
                content = self.fetch_url("https://news.ycombinator.com/")
                if content and "error" not in content.lower():
                    return f"Source: news.ycombinator.com\n\n{content[:3000]}"
            except Exception:
                pass

        # Product Hunt
        if "product hunt" in q or "new products" in q:
            try:
                content = self.fetch_url("https://www.producthunt.com/")
                if content and "error" not in content.lower():
                    return f"Source: producthunt.com\n\n{content[:3000]}"
            except Exception:
                pass

        # Generic news
        if "news" in q or "latest" in q:
            try:
                from lirox.tools.search.duckduckgo import search_ddg
                news = search_ddg(f"{query} site:reuters.com OR site:bbc.com OR site:techcrunch.com")
                if news and "error" not in news.lower():
                    return f"News search:\n{news}"
            except Exception:
                pass

        return ""

    def _multi_search(self, query: str) -> str:
        results = []
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            r = search_ddg(query)
            if r and "error" not in r.lower():
                results.append(f"## DuckDuckGo\n{r}")
        except Exception as e:
            from lirox.utils.structured_logger import get_logger
            get_logger("lirox.agents.research").warning(f"DDG error: {e}")
        try:
            from lirox.tools.search.tavily import search_tavily
            r = search_tavily(query)
            if r:
                results.append(f"## Tavily\n{r}")
        except Exception as e:
            from lirox.utils.structured_logger import get_logger
            get_logger("lirox.agents.research").warning(f"Tavily error: {e}")

        if not results:
            return "No search results available. Answering from training data."
        return "\n\n".join(results)
