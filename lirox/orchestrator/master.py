"""Lirox v3.0 — Master Orchestrator: Mode-aware, Session-managed, Isolated agents"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, Optional

from lirox.config import THINKING_ENABLED, ThinkingMode
from lirox.memory.manager import MemoryManager
from lirox.memory.session_store import SessionStore
from lirox.thinking.scratchpad import Scratchpad


class AgentType(Enum):
    FINANCE  = "finance"
    CODE     = "code"
    BROWSER  = "browser"
    RESEARCH = "research"
    CHAT     = "chat"


@dataclass
class OrchestratorEvent:
    type:      str
    agent:     str = ""
    message:   str = ""
    data:      Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MasterOrchestrator:
    def __init__(self, profile_data: Dict[str, Any] = None):
        self.profile_data   = profile_data or {}
        self.global_memory  = MemoryManager()       # shared cross-agent context
        self.session_store  = SessionStore()
        self.thinking_mode  = ThinkingMode.THINK
        self._agents:        Dict[AgentType, Any] = {}
        self._agent_memory:  Dict[AgentType, MemoryManager] = {}   # per-agent isolated memory
        self._agent_scratch: Dict[AgentType, Scratchpad] = {}      # per-agent scratchpad

    # ── Skills Wiring ─────────────────────────────────────────────────────────

    def _load_skills_for_agent(self, agent_type: AgentType, agent) -> None:
        """Wire the skills registry to an agent."""
        try:
            from lirox.skills import SkillRegistry
            registry = SkillRegistry()
            skills   = registry.get_skills_for_agent(agent_type.value)
            if skills and hasattr(agent, 'skills'):
                agent.skills = skills
        except ImportError:
            pass  # Skills system not installed — non-fatal
        except Exception as e:
            from lirox.utils.structured_logger import get_logger
            get_logger("lirox.orchestrator").warning(f"Skills wiring error: {e}")

    # ── Agent Isolation ───────────────────────────────────────────────────────

    def _get_agent_memory(self, t: AgentType) -> MemoryManager:
        if t not in self._agent_memory:
            self._agent_memory[t] = MemoryManager(agent_name=t.value)
        return self._agent_memory[t]

    def _get_agent_scratchpad(self, t: AgentType) -> Scratchpad:
        if t not in self._agent_scratch:
            self._agent_scratch[t] = Scratchpad()
        return self._agent_scratch[t]

    def _get_agent(self, t: AgentType):
        if t not in self._agents:
            mem = self._get_agent_memory(t)
            sp  = self._get_agent_scratchpad(t)
            if t == AgentType.FINANCE:
                from lirox.agents.finance_agent import FinanceAgent
                self._agents[t] = FinanceAgent(mem, sp, self.profile_data)
            elif t == AgentType.CODE:
                from lirox.agents.code_agent import CodeAgent
                self._agents[t] = CodeAgent(mem, sp, self.profile_data)
            elif t == AgentType.BROWSER:
                from lirox.agents.browser_agent import BrowserAgent
                self._agents[t] = BrowserAgent(mem, sp, self.profile_data)
            elif t == AgentType.RESEARCH:
                from lirox.agents.research_agent import ResearchAgent
                self._agents[t] = ResearchAgent(mem, sp, self.profile_data)
            else:
                from lirox.agents.chat_agent import ChatAgent
                self._agents[t] = ChatAgent(mem, sp, self.profile_data)
            self._load_skills_for_agent(t, self._agents[t])
        return self._agents[t]

    # ── Intent Classification ─────────────────────────────────────────────────

    def classify_intent(self, query: str) -> AgentType:
        q = query.lower()

        # URL → always browser
        if re.search(r"https?://\S+", q):
            return AgentType.BROWSER

        # Bigram and contextual scoring
        scores = {
            AgentType.FINANCE: 0,
            AgentType.CODE:    0,
            AgentType.BROWSER: 0,
            AgentType.RESEARCH: 0,
        }

        # Finance — specific financial terms (avoid collision with "create plan")
        finance_terms = [
            "stock", "price of", "market cap", "ticker", "earnings", "revenue",
            "p/e ratio", "dividend", "portfolio", "invest in", "trade",
            "crypto", "bitcoin", "forex", "valuation", "dcf", "eps",
            "balance sheet", "income statement", "cash flow", "sec filing",
            "analyst", "screener", "insider", "bond", "yield", "nasdaq",
            "s&p 500", "dow jones", "etf", "ipo", "bull market", "bear market",
            "margin of safety", "intrinsic value", "financial",
        ]
        for k in finance_terms:
            if k in q:
                scores[AgentType.FINANCE] += 2

        # Ticker detection: uppercase 2-5 letter words (AAPL, TSLA, BTC)
        tickers = re.findall(r'\b[A-Z]{2,5}\b', query)
        if tickers:
            scores[AgentType.FINANCE] += len(tickers)

        # Code — programming-specific (avoid "write report" going to code)
        code_specific = [
            "python", "javascript", "typescript", "react", "flask", "django",
            "dockerfile", "sql query", "debug this", "fix the bug", "refactor",
            "write a function", "write a class", "write a script",
            "write code", "compile", "build the", "deploy", "git commit",
            "unit test", "api endpoint", "database schema", "algorithm",
            "run command", "execute", "terminal", "bash script",
            "write file", "read file", "create file", "folder structure",
            "desktop", "screen", "screenshot", "click", "open ", "launch ",
            "type ", "press ",
        ]
        for k in code_specific:
            if k in q:
                scores[AgentType.CODE] += 2

        # Browser — explicit navigation / live data
        browser_terms = [
            "browse to", "navigate to", "scrape", "fill form", "login to", "sign in to",
            "trending on github", "trending on", "live data", "real-time",
            "search the web", "find on the internet",
        ]
        for k in browser_terms:
            if k in q:
                scores[AgentType.BROWSER] += 2

        # Research — deep analysis, comparison, comprehensive
        research_terms = [
            "research", "deep dive", "comprehensive analysis", "compare",
            "report on", "detailed study", "findings", "everything about",
            "literature review", "investigate", "who is", "what is the history",
            "how does", "explain in detail", "summarize", "overview of",
        ]
        for k in research_terms:
            if k in q:
                scores[AgentType.RESEARCH] += 2

        best  = max(scores, key=scores.get)
        score = scores[best]
        return best if score >= 2 else AgentType.CHAT

    # ── Mode-Aware Thinking ───────────────────────────────────────────────────

    def _build_thinking_trace(self, query: str, mode: str) -> str:
        if mode == ThinkingMode.FAST:
            return ""  # No thinking for fast mode

        context = self.global_memory.get_relevant_context(query)
        try:
            from lirox.thinking.chain_of_thought import ThinkingEngine
            return ThinkingEngine().reason(query, context)
        except Exception:
            return ""

    # ── Main Run ─────────────────────────────────────────────────────────────

    def run(
        self, query: str, system_prompt: str = "", mode: str = None, agent_override: str = None
    ) -> Generator[OrchestratorEvent, None, None]:

        mode  = mode or self.thinking_mode
        start = time.time()

        # ── Session tracking
        session = self.session_store.current()
        session.add("user", query, agent=session.active_agent, mode=mode)

        # ── Thinking phase (skip for FAST mode)
        thinking_trace = ""
        if THINKING_ENABLED and mode != ThinkingMode.FAST:
            yield OrchestratorEvent(type="thinking", message="Analyzing...")
            try:
                thinking_trace = self._build_thinking_trace(query, mode)
                if thinking_trace:
                    yield OrchestratorEvent(type="thinking", message=thinking_trace)
            except Exception as e:
                from lirox.utils.structured_logger import get_logger
                get_logger("lirox.orchestrator").warning(f"Thinking engine error: {e}")

        # ── Route to agent
        if agent_override:
            try:
                agent_type = AgentType(agent_override.lower())
            except ValueError:
                agent_type = AgentType(session.active_agent)
        else:
            try:
                agent_type = AgentType(session.active_agent)
            except ValueError:
                agent_type = AgentType.CHAT

        # For COMPLEX mode, override agent system prompt with structured output requirement
        if mode == ThinkingMode.COMPLEX:
            system_prompt = (
                system_prompt or ""
            ) + "\n\nOUTPUT FORMAT (REQUIRED):\n"  \
              "## 🎯 Direct Answer\n[Answer the question directly]\n\n"  \
              "## 🧠 Reasoning & Analysis\n[Your analysis and reasoning]\n\n"  \
              "## 📋 Recommended Plan\n[Step-by-step action plan if applicable]\n\n"  \
              "## 💡 My Recommendation\n[Your concrete recommendation]\n\n"  \
              "## ⚠️ Key Risks / Caveats\n[Important warnings or limitations]"

        yield OrchestratorEvent(
            type="agent_start",
            agent=agent_type.value,
            message=f"[{mode.upper()}] Routing to {agent_type.value} agent",
        )

        # Update session's active agent
        session.active_agent = agent_type.value

        agent       = self._get_agent(agent_type)
        result_text = ""

        try:
            for event in agent.run(
                query,
                system_prompt=system_prompt,
                context=thinking_trace,
                mode=mode,
            ):
                yield OrchestratorEvent(
                    type    = event.get("type", "agent_progress"),
                    agent   = agent_type.value,
                    message = event.get("message", ""),
                    data    = event,
                )
                if event.get("type") == "done":
                    result_text = event.get("answer", "")
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        # ── Persist
        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent=agent_type.value, mode=mode)
        self.session_store.save_current()

        yield OrchestratorEvent(
            type    = "done",
            message = result_text,
            data    = {
                "agents_used": [agent_type.value],
                "total_time":  time.time() - start,
                "mode":        mode,
            },
        )

    # ── Mode Switching ────────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> bool:
        valid = {ThinkingMode.FAST, ThinkingMode.THINK, ThinkingMode.COMPLEX}
        if mode.lower() in valid:
            self.thinking_mode = mode.lower()
            # Start a new session when mode changes
            self.session_store.new_session(
                agent=self.session_store.current().active_agent,
                mode=mode.lower()
            )
            return True
        return False

    def set_agent(self, agent_name: str) -> bool:
        mapping = {
            "finance":  AgentType.FINANCE,
            "code":     AgentType.CODE,
            "browser":  AgentType.BROWSER,
            "research": AgentType.RESEARCH,
            "chat":     AgentType.CHAT,
        }
        if agent_name.lower() in mapping:
            agent_type = mapping[agent_name.lower()]
            # Start new session on agent switch
            session = self.session_store.new_session(
                agent=agent_name.lower(),
                mode=self.thinking_mode
            )
            return True
        return False
