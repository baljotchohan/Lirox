"""Lirox — Master Orchestrator: Session-managed, isolated agents, always-on deep thinking"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, Optional

from lirox.config import THINKING_ENABLED
from lirox.memory.manager import MemoryManager
from lirox.memory.session_store import SessionStore
from lirox.thinking.scratchpad import Scratchpad

# COMPLEX format instructions injected into all agent calls via context
COMPLEX_FORMAT_SUFFIX = (
    "\n\n---\nOUTPUT FORMAT (REQUIRED):\n"
    "## 🎯 Direct Answer\n[Answer the question directly]\n\n"
    "## 🧠 Reasoning & Analysis\n[Your analysis and reasoning]\n\n"
    "## 📋 Recommended Plan\n[Step-by-step action plan if applicable]\n\n"
    "## 💡 My Recommendation\n[Your concrete recommendation]\n\n"
    "## ⚠️ Key Risks / Caveats\n[Important warnings or limitations]"
)

# Agent identity header — prevents hallucination and role confusion
AGENT_IDENTITY_HEADER = """
═══════════════════════════════════════════
  YOU ARE: {agent_name} — {agent_role}
  NEVER pretend to be another agent.
  NEVER route tasks to other agents in your response.
  NEVER say "I'll hand this to the Finance Agent" etc.
  If the task is outside your domain, say so clearly.
═══════════════════════════════════════════
"""


class AgentType(Enum):
    FINANCE  = "finance"
    CODE     = "code"
    BROWSER  = "browser"
    RESEARCH = "research"
    CHAT     = "chat"  # handled directly by orchestrator


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
        self.global_memory  = MemoryManager()
        self.session_store  = SessionStore()
        self._agents:        Dict[AgentType, Any] = {}
        self._agent_memory:  Dict[AgentType, MemoryManager] = {}
        self._agent_scratch: Dict[AgentType, Scratchpad] = {}

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
            pass
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
                # CHAT — direct orchestrator answer, no specialist agent
                return None
            self._load_skills_for_agent(t, self._agents[t])
        return self._agents.get(t)

    # ── Intent Classification ─────────────────────────────────────────────────

    def classify_intent(self, query: str) -> AgentType:
        """BUG-01/06 FIX: Always called for every query when no explicit agent override."""
        q = query.lower()

        # URL → always browser
        if re.search(r"https?://\S+", q):
            return AgentType.BROWSER

        scores = {
            AgentType.FINANCE:  0,
            AgentType.CODE:     0,
            AgentType.BROWSER:  0,
            AgentType.RESEARCH: 0,
        }

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

        # Ticker detection: uppercase 2-5 letter words
        tickers = re.findall(r'\b[A-Z]{2,5}\b', query)
        if tickers:
            scores[AgentType.FINANCE] += len(tickers)

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

        browser_terms = [
            "browse to", "navigate to", "scrape", "fill form", "login to", "sign in to",
            "trending on github", "trending on", "live data", "real-time",
            "search the web", "find on the internet",
        ]
        for k in browser_terms:
            if k in q:
                scores[AgentType.BROWSER] += 2

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

    def needs_agent(self, query: str) -> bool:
        """
        BUG-06 FIX: True only if this query requires a specialist agent with tools.
        Pure conversational queries are answered directly by the orchestrator.
        """
        task_signals = [
            # code
            "write", "create", "build", "fix", "debug", "run", "execute", "deploy",
            "refactor", "test", "generate code", "make a",
            # finance
            "stock", "price", "trade", "invest", "portfolio", "ticker", "market",
            "analyze", "valuation", "crypto", "bitcoin",
            # research
            "research", "find", "search", "look up", "what is", "who is",
            "latest news", "trending", "investigate",
            # desktop
            "open", "click", "screenshot", "screen", "desktop", "launch", "type",
            "navigate to", "use my computer",
        ]
        q = query.lower()
        return any(sig in q for sig in task_signals)

    # ── Thinking Engine ───────────────────────────────────────────────────────

    def _build_thinking_trace(self, query: str) -> str:
        """Always builds a thinking trace — deep thinking is always-on."""
        context = self.global_memory.get_relevant_context(query)
        try:
            from lirox.thinking.chain_of_thought import ThinkingEngine
            return ThinkingEngine().reason(query, context)
        except Exception:
            return ""

    # ── Soul / Identity ───────────────────────────────────────────────────────

    def _get_identity_prompt(self) -> str:
        try:
            from lirox.soul import get_identity_prompt
            return get_identity_prompt()
        except Exception:
            return "You are Lirox, an autonomous AI agent. Be helpful, precise, and direct."

    # ── Main Run ─────────────────────────────────────────────────────────────

    def run(
        self, query: str, system_prompt: str = "", mode: str = None, agent_override: str = None
    ) -> Generator[OrchestratorEvent, None, None]:
        # mode param kept for API compatibility but always treated as "complex" internally
        start = time.time()

        session = self.session_store.current()
        session.add("user", query, agent=session.active_agent, mode="complex")

        # ── Thinking phase (always-on) ─────────────────────────────────────
        thinking_trace = ""
        if THINKING_ENABLED:
            yield OrchestratorEvent(type="thinking", message="Analyzing...")
            try:
                thinking_trace = self._build_thinking_trace(query)
                if thinking_trace:
                    yield OrchestratorEvent(type="thinking", message=thinking_trace)
            except Exception as e:
                from lirox.utils.structured_logger import get_logger
                get_logger("lirox.orchestrator").warning(f"Thinking engine error: {e}")

        # ── Route to agent ────────────────────────────────────────────────
        # FIX: Only use agents when user explicitly chooses OR query has task signals

        if agent_override:
            # User ran /agent command — respect it
            try:
                agent_type = AgentType(agent_override.lower())
            except ValueError:
                agent_type = AgentType.CHAT
        elif session.agent_explicitly_set:
            # User manually set agent via /agent — stick with it
            try:
                agent_type = AgentType(session.active_agent)
            except ValueError:
                agent_type = AgentType.CHAT
        else:
            # NEW: Only classify if query HAS task signals
            if self.needs_agent(query):
                agent_type = self.classify_intent(query)
            else:
                agent_type = AgentType.CHAT  # Default to chat

        # Update session's active agent (persist the "sticky" agent)
        session.active_agent = agent_type.value

        # ── Direct conversational answer (no specialist agent needed) ──────
        if agent_type == AgentType.CHAT or (
            not session.agent_explicitly_set and not self.needs_agent(query)
        ):
            yield OrchestratorEvent(
                type="agent_start", agent="chat",
                message="Answering directly"
            )
            try:
                from lirox.utils.llm import generate_response
                identity = self._get_identity_prompt()
                prompt = query
                if thinking_trace:
                    prompt = f"Thinking:\n{thinking_trace}\n\nUser: {query}"
                direct_answer = generate_response(
                    prompt,
                    provider="auto",
                    system_prompt=identity + COMPLEX_FORMAT_SUFFIX,
                )
                self.global_memory.save_exchange(query, direct_answer)
                session.add("assistant", direct_answer, agent="chat", mode="complex")
                self.session_store.save_current()
                yield OrchestratorEvent(
                    type="done",
                    agent="chat",
                    message=direct_answer,
                    data={"agents_used": ["chat"], "total_time": time.time() - start},
                )
            except Exception as e:
                yield OrchestratorEvent(type="error", message=str(e))
            return

        # ── Specialist agent routing ───────────────────────────────────────
        yield OrchestratorEvent(
            type="agent_start",
            agent=agent_type.value,
            message=f"Routing to {agent_type.value} agent",
        )

        # BUG-15 FIX: Inject COMPLEX format via context param, not system_prompt
        # (agents that build their own system_prompt would ignore passed system_prompt)
        complex_context = thinking_trace
        if complex_context:
            complex_context += COMPLEX_FORMAT_SUFFIX
        else:
            complex_context = COMPLEX_FORMAT_SUFFIX.strip()

        agent       = self._get_agent(agent_type)
        result_text = ""

        try:
            for event in agent.run(
                query,
                system_prompt=system_prompt,
                context=complex_context,
                mode="complex",          # BUG-02: always pass mode
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

        # ── Persist ──────────────────────────────────────────────────────
        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent=agent_type.value, mode="complex")
        self.session_store.save_current()

        yield OrchestratorEvent(
            type    = "done",
            message = result_text,
            data    = {
                "agents_used": [agent_type.value],
                "total_time":  time.time() - start,
                "mode":        "complex",
            },
        )

    # ── Agent Switching ───────────────────────────────────────────────────────

    def set_agent(self, agent_name: str) -> bool:
        mapping = {
            "finance":  AgentType.FINANCE,
            "code":     AgentType.CODE,
            "browser":  AgentType.BROWSER,
            "research": AgentType.RESEARCH,
            "chat":     AgentType.CHAT,
        }
        if agent_name.lower() in mapping:
            session = self.session_store.current()
            # Mark current session as explicit if we aren't creating a fresh one, 
            # though set_agent usually starts a new one.
            session.active_agent = agent_name.lower()
            session.agent_explicitly_set = True
            
            # Start fresh session with the chosen agent and explicit flag
            self.session_store.new_session(
                agent=agent_name.lower(),
                mode="complex",
                explicit=True
            )
            return True
        return False
