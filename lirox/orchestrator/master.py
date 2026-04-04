"""Lirox v2.0 — Master Orchestrator: Intent → Route → Aggregate"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator

from lirox.config import THINKING_ENABLED
from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad


class AgentType(Enum):
    FINANCE = "finance"
    CODE = "code"
    BROWSER = "browser"
    RESEARCH = "research"
    CHAT = "chat"


@dataclass
class OrchestratorEvent:
    type: str
    agent: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MasterOrchestrator:
    def __init__(self, profile_data: Dict[str, Any] = None):
        self.profile_data = profile_data or {}
        self.memory = MemoryManager()
        self.scratchpad = Scratchpad()
        self._agents: Dict[AgentType, Any] = {}

    def _get_agent(self, t: AgentType):
        if t not in self._agents:
            if t == AgentType.FINANCE:
                from lirox.agents.finance_agent import FinanceAgent
                self._agents[t] = FinanceAgent(self.memory, self.scratchpad)
            elif t == AgentType.CODE:
                from lirox.agents.code_agent import CodeAgent
                self._agents[t] = CodeAgent(self.memory, self.scratchpad)
            elif t == AgentType.BROWSER:
                from lirox.agents.browser_agent import BrowserAgent
                self._agents[t] = BrowserAgent(self.memory, self.scratchpad)
            elif t == AgentType.RESEARCH:
                from lirox.agents.research_agent import ResearchAgent
                self._agents[t] = ResearchAgent(self.memory, self.scratchpad)
            else:
                from lirox.agents.chat_agent import ChatAgent
                self._agents[t] = ChatAgent(self.memory, self.scratchpad)
        return self._agents[t]

    def classify_intent(self, query: str) -> AgentType:
        q = query.lower()
        scores = {
            AgentType.FINANCE: sum(
                1
                for k in [
                    "stock", "price", "market", "ticker", "earnings", "revenue",
                    "p/e", "dividend", "portfolio", "invest", "trade", "crypto",
                    "bitcoin", "forex", "valuation", "dcf", "eps", "balance sheet",
                    "income statement", "cash flow", "sec filing", "analyst",
                    "screener", "insider", "bond", "yield", "$", "nasdaq",
                    "s&p", "dow", "etf", "ipo",
                ]
                if k in q
            ),
            AgentType.CODE: sum(
                1
                for k in [
                    "code", "script", "function", "class", "debug", "fix bug",
                    "refactor", "implement", "algorithm", "api", "endpoint",
                    "database", "sql", "python", "javascript", "react", "flask",
                    "django", "dockerfile", "test", "lint", "compile", "build",
                    "deploy", "git", "review code", "architecture", "package",
                    "syntax", "error", "exception", "import",
                ]
                if k in q
            ),
            AgentType.BROWSER: sum(
                1
                for k in [
                    "browse", "navigate", "click", "webpage", "website", "open url",
                    "screenshot", "scrape page", "fill form", "login to",
                    "sign in", "download from", "interactive",
                ]
                if k in q
            ),
            AgentType.RESEARCH: sum(
                1
                for k in [
                    "research", "investigate", "deep dive", "comprehensive",
                    "compare", "report on", "study", "findings", "everything about",
                    "detailed analysis", "literature review",
                ]
                if k in q
            ),
        }
        if re.search(r"https?://\S+", q):
            scores[AgentType.BROWSER] += 3
        best = max(scores, key=scores.get)
        return best if scores[best] >= 1 else AgentType.CHAT

    def run(
        self, query: str, system_prompt: str = ""
    ) -> Generator[OrchestratorEvent, None, None]:
        start = time.time()
        thinking_trace = ""

        if THINKING_ENABLED:
            yield OrchestratorEvent(type="thinking", message="Analyzing...")
            try:
                from lirox.thinking.chain_of_thought import ThinkingEngine

                thinking_trace = ThinkingEngine().reason(
                    query, self.memory.get_relevant_context(query)
                )
                yield OrchestratorEvent(type="thinking", message=thinking_trace)
            except Exception:
                pass

        agent_type = self.classify_intent(query)
        yield OrchestratorEvent(
            type="agent_start",
            agent=agent_type.value,
            message=f"Routing to {agent_type.value} agent",
        )

        agent = self._get_agent(agent_type)
        result_text = ""
        try:
            for event in agent.run(query, system_prompt=system_prompt, context=thinking_trace):
                yield OrchestratorEvent(
                    type=event.get("type", "agent_progress"),
                    agent=agent_type.value,
                    message=event.get("message", ""),
                    data=event,
                )
                if event.get("type") == "done":
                    result_text = event.get("answer", "")
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        self.memory.save_exchange(query, result_text)
        yield OrchestratorEvent(
            type="done",
            message=result_text,
            data={
                "agents_used": [agent_type.value],
                "total_time": time.time() - start,
            },
        )
