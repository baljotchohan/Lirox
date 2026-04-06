"""
Lirox v3.0 — Finance Agent
Personality: Buffett + Munger value investor.
Features:
  - First interaction onboarding (asks for API setup)
  - Proactive suggestions based on past question patterns
  - Per-agent isolated memory
  - Mode-aware responses
  - Sanitized LLM tool call args
"""
from __future__ import annotations

import json
import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.config import MAX_LLM_PROMPT_CHARS, ThinkingMode

FINANCE_SYS = """You are the {agent_name} Finance Agent — a research-grade financial analyst.
Philosophy: Buffett + Munger — value investing, margin of safety, invert always invert.
Format: Lead with direct answer. Use compact tables for data (Rev, OM, EPS, P/E, FCF).
Date: {date}
{user_context}"""

ONBOARDING_MSG = """📊 **Welcome to your Finance Agent!**

I'm your personal financial analyst — but I'm still learning your style.

To make me more powerful, you can add:
  • **`FINANCIAL_DATASETS_API_KEY`** — Real SEC filings, fundamentals data
  • **`TAVILY_API_KEY`** — Real-time financial news and research

Without these, I'll use yfinance for live prices and my own analysis.

**How would you like me to greet you?** I'll remember your preferences as we work together.

What's your first financial question?"""

PROACTIVE_TEMPLATES = [
    "💡 Last time you asked about **{topic}** — want a quick update on today's price/news?",
    "📈 You've been tracking **{topic}** — here's what I'd check first today:",
    "🔍 Based on your research pattern, you might also want to look at **{topic}**.",
]


class FinanceAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return "Market analysis, stock research, portfolio insights, valuation"

    def get_onboarding_message(self) -> str:
        return ONBOARDING_MSG

    def _get_proactive_greeting(self) -> str:
        """Generate a proactive greeting based on past question patterns."""
        patterns = self.memory.get_pattern_insights(limit=1)
        if not patterns:
            return ""
        topic = patterns[0].upper()
        import random
        template = random.choice(PROACTIVE_TEMPLATES)
        return template.format(topic=topic)

    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = ThinkingMode.THINK
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time
        from datetime import datetime

        logger = get_logger(f"lirox.agents.{self.name}")
        start  = time.time()
        log_with_metadata(logger, "INFO", "Finance Agent started", query=query[:100], mode=mode)



        # ── Subsequent sessions: proactive greeting
        if len(self.memory.conversation_buffer) > 0:
            greeting = self._get_proactive_greeting()
            if greeting:
                yield {"type": "agent_progress", "message": greeting}

        yield {"type": "agent_progress", "message": "Finance Agent analyzing..."}

        # Build system prompt
        agent_name   = self.profile_data.get("agent_name", "Lirox")
        user_context = ""
        mem_ctx      = self.memory.get_relevant_context(query)
        if mem_ctx:
            user_context = f"User Context:\n{mem_ctx}"

        sys_p = FINANCE_SYS.format(
            agent_name   = agent_name,
            date         = datetime.now().strftime("%B %d, %Y"),
            user_context = user_context,
        )

        if mode == ThinkingMode.FAST:
            sys_p += "\n\nBe concise — give the key number and one-sentence analysis."

        # ── Tool routing via LLM
        routing_resp = generate_response(
            f"Return a JSON array of tool calls needed for this query: {query}\n"
            f"Available tools: market_data, fundamentals, screener, web_search\n"
            f"Each tool call: {{\"tool\": \"name\", \"args\": {{...}}}}\n"
            f"Return ONLY valid JSON array, no other text.",
            provider="auto",
            system_prompt="You are a tool router. Return ONLY a valid JSON array.",
        )
        tools = self._parse_tools(routing_resp)

        results = []
        if tools:
            for tc in tools:
                tool_name = tc.get("tool") or tc.get("name") or tc.get("function") or ""
                tool_args = tc.get("args") or tc.get("arguments") or {}
                if not tool_name:
                    continue
                yield {"type": "tool_call", "message": f"Fetching {tool_name}..."}
                # Sanitize args before passing to tools
                tool_args = self._sanitize_args(tool_name, tool_args)
                r = self._exec(tool_name, tool_args)
                results.append({"tool": tool_name, "result": r})
                self.scratchpad.add_tool_result(tool_name, r)
                yield {"type": "tool_result", "message": f"{tool_name}: done"}

        # ── Direct yfinance fallback
        if not results:
            tickers     = re.findall(r'\b([A-Z]{2,5})\b', query)
            direct_data = []
            try:
                import yfinance as yf
                for ticker in tickers[:3]:
                    if re.match(r'^[A-Z]{2,5}$', ticker):
                        info  = yf.Ticker(ticker).fast_info
                        price = getattr(info, 'last_price', None)
                        if price:
                            direct_data.append(f"{ticker}: ${price:,.2f}")
                if "bitcoin" in query.lower() or "btc" in query.lower():
                    btc = getattr(yf.Ticker("BTC-USD").fast_info, 'last_price', None)
                    if btc:
                        direct_data.append(f"Bitcoin (BTC): ${btc:,.2f}")
            except Exception:
                pass
            if direct_data:
                results.append({"tool": "yfinance", "result": "\n".join(direct_data)})

        # ── Synthesize
        yield {"type": "agent_progress", "message": "Synthesizing analysis..."}
        if results:
            synth_prompt = (
                f"Query: {query}\n"
                f"Data:\n{json.dumps(results, indent=2, default=str)[:MAX_LLM_PROMPT_CHARS]}"
            )
            if context:
                synth_prompt += f"\n\nReasoning context:\n{context}"
        else:
            synth_prompt = query
            if context:
                synth_prompt = f"Reasoning:\n{context}\n\n{synth_prompt}"

        answer = generate_response(synth_prompt, provider="auto", system_prompt=sys_p)
        self.memory.save_exchange(query, answer)

        log_with_metadata(logger, "INFO", "Finance Agent completed",
                          duration_ms=int((time.time() - start) * 1000))
        yield {"type": "done", "answer": answer, "sources": []}

    def _sanitize_args(self, tool: str, args: dict) -> dict:
        """Sanitize tool args to prevent injection. BUG-05 fix."""
        safe = {}
        if tool in ("market_data", "web_search"):
            q = str(args.get("query", ""))[:200]
            q = re.sub(r'[^\w\s\-.,?!$%]', '', q)
            safe["query"] = q
        elif tool == "fundamentals":
            ticker = str(args.get("ticker", "")).upper()
            if re.match(r'^[A-Z]{1,5}(-USD)?$', ticker):
                safe["ticker"] = ticker
            else:
                safe["ticker"] = ""
        elif tool == "screener":
            criteria = str(args.get("criteria", ""))[:200]
            safe["criteria"] = criteria
        return safe

    def _parse_tools(self, text: str) -> list:
        text = re.sub(r"```json?\s*", "", text.strip())
        text = re.sub(r"```\s*", "", text)
        try:
            r = json.loads(text)
            return r if isinstance(r, list) else []
        except Exception:
            pass
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return []

    ALLOWED_TOOLS = {"market_data", "fundamentals", "screener", "web_search"}

    def _exec(self, tool: str, args: dict) -> str:
        if tool not in self.ALLOWED_TOOLS:
            return f"Blocked unknown tool: {tool}"
        try:
            if tool == "market_data":
                from lirox.tools.finance.market_data import get_market_data
                return get_market_data(args.get("query", ""))
            elif tool == "fundamentals":
                from lirox.tools.finance.fundamentals import get_fundamentals
                return get_fundamentals(args.get("ticker", ""))
            elif tool == "screener":
                from lirox.tools.finance.screener import screen_stocks
                return screen_stocks(args.get("criteria", ""))
            elif tool == "web_search":
                from lirox.tools.search.duckduckgo import search_ddg
                return search_ddg(args.get("query", ""))
        except Exception as e:
            return f"Tool error ({tool}): {e}"
        return f"Unknown tool: {tool}"
