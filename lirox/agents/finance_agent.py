"""Finance Agent — Dexter-inspired market analysis with tool routing."""
from __future__ import annotations

import json
import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response

FINANCE_SYS = """You are the Finance Agent — a research-grade financial analyst.
Philosophy: Buffett + Munger — value investing, margin of safety, invert always invert.
Format: Compact tables (Rev, OM, EPS, P/E, FCF). Lead with answer, then data."""


class FinanceAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return "Market analysis, stock research, portfolio insights"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        from datetime import datetime

        sys_p = FINANCE_SYS + f"\nDate: {datetime.now().strftime('%B %d, %Y')}"
        mem = self.memory.search("portfolio risk investment", limit=3)
        if mem:
            sys_p += f"\n\nUser Context:\n{mem}"

        yield {"type": "agent_progress", "message": "Finance Agent analyzing..."}

        routing = generate_response(
            f"Return JSON array of tool calls for: {query}\n"
            f"Tools: market_data, fundamentals, screener, web_search\nJSON:",
            provider="auto",
            system_prompt="Return ONLY valid JSON array.",
        )
        tools = self._parse(routing)

        if tools:
            results = []
            for tc in tools:
                yield {"type": "tool_call", "message": f"Fetching {tc['tool']}..."}
                r = self._exec(tc["tool"], tc.get("args", {}))
                results.append({"tool": tc["tool"], "result": r})
                self.scratchpad.add_tool_result(tc["tool"], r)
                yield {"type": "tool_result", "message": f"{tc['tool']}: done"}

            yield {"type": "agent_progress", "message": "Synthesizing..."}
            synth = (
                f"Query: {query}\n"
                f"Data:\n{json.dumps(results, indent=2, default=str)[:8000]}"
            )
            answer = generate_response(synth, provider="auto", system_prompt=sys_p)
        else:
            answer = generate_response(query, provider="auto", system_prompt=sys_p)

        yield {"type": "done", "answer": answer, "sources": []}

    def _parse(self, text: str) -> list:
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

    def _exec(self, tool: str, args: dict) -> str:
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
            return f"Unknown tool: {tool}"
        except Exception as e:
            return f"Error ({tool}): {e}"
