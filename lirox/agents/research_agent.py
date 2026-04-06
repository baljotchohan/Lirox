"""
Lirox — Research Agent
5-stage research pipeline: Planner → Multi-Source Searcher → Fact Extractor → Cross-Validator → Synthesizer
Perplexity-style terminal research with multi-source synthesis.
"""
from __future__ import annotations

import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.config import MAX_LLM_PROMPT_CHARS

RESEARCH_SYS = """
═══════════════════════════════════════════
  YOU ARE: {agent_name} Research Agent
  IDENTITY: Perplexity-style deep researcher
  NEVER pretend to be another agent.
═══════════════════════════════════════════

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

ONBOARDING_MSG = """🔬 **Research Agent — Perplexity in your terminal!**

I search the web, synthesize multiple sources, and give you verified, cited answers.

5-stage pipeline on every query:
1. Research Planner — maps search strategy
2. Multi-Source Searcher — DuckDuckGo + Tavily + direct fetch
3. Fact Extractor — pulls out key data points
4. Cross-Validator — checks source consistency
5. Synthesizer — builds final cited answer

To make me more powerful:
  • **`TAVILY_API_KEY`** — Premium research-grade search results

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
        self, query: str, system_prompt: str = "", context: str = "", mode: str = "complex"
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time

        logger = get_logger(f"lirox.agents.{self.name}")
        start  = time.time()
        log_with_metadata(logger, "INFO", "Research Agent started", query=query[:100])

        # Sub-agent 1: Query Planner
        yield {"type": "agent_progress", "message": "🗺️  Planning research strategy..."}
        plan = self._plan_research(query)
        yield {"type": "tool_result", "message": plan[:100]}

        # Sub-agent 2: Multi-Source Searcher
        yield {"type": "agent_progress", "message": "🔍 Searching multiple sources..."}
        raw_results = self._multi_search(query)
        yield {"type": "tool_result", "message": f"Retrieved {len(raw_results)} chars of source data"}

        # Sub-agent 3: Live Data (GitHub, HN, news)
        if self._is_live_query(query):
            yield {"type": "tool_call", "message": "📡 Fetching live data..."}
            live_data = self._fetch_live_data(query)
            if live_data:
                raw_results = f"## Live Data\n{live_data}\n\n" + raw_results
                yield {"type": "tool_result", "message": f"✅ Live data retrieved"}

        # Sub-agent 4: Fact Extractor
        yield {"type": "agent_progress", "message": "📌 Extracting key facts..."}
        facts = self._extract_facts(query, raw_results)

        # Sub-agent 5: Cross-Validator
        yield {"type": "agent_progress", "message": "⚖️  Cross-validating sources..."}
        validated = self._cross_validate(query, facts, raw_results)

        # Sub-agent 6: Synthesizer
        yield {"type": "agent_progress", "message": "🧠 Synthesizing final answer..."}

        agent_name = self.profile_data.get("agent_name", "Lirox")
        sys_p      = RESEARCH_SYS.format(agent_name=agent_name)

        prompt = (
            f"Research Query: {query}\n\n"
            f"Research Plan: {plan}\n\n"
            f"Key Facts Extracted:\n{facts}\n\n"
            f"Cross-Validation Notes:\n{validated}\n\n"
            f"Source Data (truncated):\n{raw_results[:3000]}\n\n"
            f"Synthesize comprehensively. Cross-reference sources. Note conflicts between sources."
        )
        if context:
            prompt += f"\n\nReasoning context:\n{context[:800]}"

        if not raw_results or "No results" in raw_results:
            prompt += "\n\nNOTE: Web search returned no results. Answer from training data and clearly caveat."

        answer = generate_response(prompt[:MAX_LLM_PROMPT_CHARS], provider="auto", system_prompt=sys_p)
        self.memory.save_exchange(query, answer)

        log_with_metadata(logger, "INFO", "Research Agent completed",
                          duration_ms=int((time.time() - start) * 1000))
        yield {"type": "done", "answer": answer, "sources": []}

    # ─── Sub-Agents ───────────────────────────────────────────────────────────

    def _plan_research(self, query: str) -> str:
        """Sub-agent 1: Map the research strategy."""
        try:
            plan = generate_response(
                f"Map a research plan for: {query}\n"
                f"Output 3-5 bullet points of what to search for and where. Be concise.",
                provider="auto",
                system_prompt="You are a research strategist. Output a brief bullet-point plan only.",
            )
            return plan[:500]
        except Exception:
            return f"Search for: {query}"

    def _extract_facts(self, query: str, raw_results: str) -> str:
        """Sub-agent 3: Extract key facts from search results."""
        if not raw_results or len(raw_results) < 100:
            return "No significant facts extracted from search results."
        try:
            facts = generate_response(
                f"Query: {query}\n\nSource data:\n{raw_results[:4000]}\n\n"
                f"Extract the 5-10 most important, specific facts with their sources.",
                provider="auto",
                system_prompt="You are a fact extractor. List specific facts as bullet points. Include source URLs where present.",
            )
            return facts[:1000]
        except Exception:
            return raw_results[:500]

    def _cross_validate(self, query: str, facts: str, raw_results: str) -> str:
        """Sub-agent 4: Check consistency across sources."""
        if not facts or not raw_results:
            return "Insufficient data for cross-validation."
        try:
            validation = generate_response(
                f"Query: {query}\n\nExtracted facts:\n{facts}\n\n"
                f"Additional sources:\n{raw_results[:2000]}\n\n"
                f"Are there any contradictions between sources? What is the consensus?",
                provider="auto",
                system_prompt="You are a fact-checker. Be brief — 3-5 sentences max.",
            )
            return validation[:500]
        except Exception:
            return "Cross-validation skipped."

    def _is_live_query(self, query: str) -> bool:
        live_indicators = [
            "trending", "today", "latest", "current", "right now", "2025", "2026",
            "github trending", "news", "price of", "stock", "weather",
            "most popular", "top repos", "recent", "this week",
        ]
        q = query.lower()
        return any(k in q for k in live_indicators)

    def _fetch_live_data(self, query: str) -> str:
        q = query.lower()
        if "github" in q and ("trending" in q or "popular" in q or "repo" in q):
            try:
                content = self.fetch_url("https://github.com/trending")
                if content and "error" not in content.lower():
                    return f"Source: github.com/trending\n\n{content[:3000]}"
            except Exception:
                pass

        if "hacker news" in q or " hn " in q or "hackernews" in q:
            try:
                content = self.fetch_url("https://news.ycombinator.com/")
                if content and "error" not in content.lower():
                    return f"Source: news.ycombinator.com\n\n{content[:3000]}"
            except Exception:
                pass

        if "product hunt" in q or "new products" in q:
            try:
                content = self.fetch_url("https://www.producthunt.com/")
                if content and "error" not in content.lower():
                    return f"Source: producthunt.com\n\n{content[:3000]}"
            except Exception:
                pass

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
