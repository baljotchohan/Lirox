"""Lirox v1.0.0 — Master Orchestrator (Mind Agent Architecture)"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, Optional

from lirox.config import THINKING_ENABLED
from lirox.memory.manager import MemoryManager
from lirox.memory.session_store import SessionStore
from lirox.thinking.scratchpad import Scratchpad

COMPLEX_FORMAT_SUFFIX = (
    "\n\n---\nOUTPUT FORMAT (REQUIRED):\n"
    "## 🎯 Direct Answer\n[Answer the question directly]\n\n"
    "## 🧠 Reasoning & Analysis\n[Your analysis]\n\n"
    "## 📋 Plan / Steps\n[If applicable]\n\n"
    "## 💡 Recommendation\n[Concrete next step]\n\n"
    "## ⚠️ Risks / Caveats\n[Warnings]"
)


class AgentType(Enum):
    PERSONAL = "personal"
    MIND     = "mind"
    CHAT     = "chat"    # direct LLM, no agent overhead for simple queries
    FINANCE  = "finance"
    RESEARCH = "research"
    CODE     = "code"
    GENERAL  = "general"


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
        self.memory         = self.global_memory   # alias for test compatibility
        self.session_store  = SessionStore()
        self._agent:         Optional[Any] = None
        self._agent_memory:  Dict[AgentType, MemoryManager] = {}
        self._agent_scratch: Dict[AgentType, Scratchpad]    = {}

    # ── Agent singleton ───────────────────────────────────────────────────────

    def _get_personal_agent(self):
        if self._agent is None:
            if AgentType.PERSONAL not in self._agent_memory:
                self._agent_memory[AgentType.PERSONAL] = MemoryManager(
                    agent_name="personal"
                )
            if AgentType.PERSONAL not in self._agent_scratch:
                self._agent_scratch[AgentType.PERSONAL] = Scratchpad()
            from lirox.agents.personal_agent import PersonalAgent
            self._agent = PersonalAgent(
                memory       = self._agent_memory[AgentType.PERSONAL],
                scratchpad   = self._agent_scratch[AgentType.PERSONAL],
                profile_data = self.profile_data,
            )
        return self._agent

    def _get_mind_agent(self):
        if getattr(self, "_mind_agent", None) is None:
            if AgentType.MIND not in self._agent_memory:
                self._agent_memory[AgentType.MIND] = MemoryManager(agent_name="mind")
            if AgentType.MIND not in self._agent_scratch:
                self._agent_scratch[AgentType.MIND] = Scratchpad()
            from lirox.mind.agent import MindAgent
            self._mind_agent = MindAgent(
                memory       = self._agent_memory[AgentType.MIND],
                scratchpad   = self._agent_scratch[AgentType.MIND],
                profile_data = self.profile_data,
            )
        return self._mind_agent

    # ── Intent Classification ──────────────────────────────────────────────────

    def classify_intent(self, query: str) -> AgentType:
        """
        Classify the intent of a query into an AgentType.

        Returns the most appropriate AgentType for routing the query.
        """
        q = query.lower()
        finance_signals = [
            "stock", "price", "ticker", "market", "share", "equity",
            "crypto", "bitcoin", "eth", "invest", "portfolio", "nasdaq",
            "nyse", "s&p", "dow", "tsla", "aapl", "btc", "usd",
        ]
        if any(s in q for s in finance_signals):
            return AgentType.FINANCE

        research_signals = ["research", "study", "paper", "article", "find info", "learn about"]
        if any(s in q for s in research_signals):
            return AgentType.RESEARCH

        code_signals = ["code", "function", "class", "bug", "debug", "programming", "script"]
        if any(s in q for s in code_signals):
            return AgentType.CODE

        return AgentType.GENERAL

    # ── Helper ────────────────────────────────────────────────────────────────

    def _get_identity_prompt(self) -> str:
        try:
            from lirox.mind.agent import get_soul, get_learnings
            learn_ctx = get_learnings().to_context_string()
            return get_soul().to_system_prompt(learn_ctx)
        except Exception:
            return "You are Lirox, an autonomous personal AI agent."

    def _build_thinking_trace(self, query: str) -> str:
        context = self.global_memory.get_relevant_context(query)
        try:
            from lirox.thinking.chain_of_thought import ThinkingEngine
            return ThinkingEngine().reason(query, context)
        except Exception:
            return ""

    # ── Needs-agent check ─────────────────────────────────────────────────────

    def _needs_agent(self, query: str) -> bool:
        """
        True if the query requires tool use (file, shell, web).
        Simple conversational queries are answered directly.
        """
        q = query.lower()
        task_signals = [
            "open", "click", "launch", "run", "execute", "create", "write",
            "read", "delete", "search", "find", "list files", "screenshot",
            "screen", "type ", "press ", "install", "download", "build",
            "navigate", "browse", "fetch", "git ", "python ", "docker",
        ]
        return any(s in q for s in task_signals)

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(
        self,
        query:          str,
        system_prompt:  str = "",
        mode:           str = None,
        agent_override: str = None,
    ) -> Generator[OrchestratorEvent, None, None]:
        start   = time.time()
        session = self.session_store.current()
        session.add("user", query, agent="personal", mode="complex")

        # ── Conversation history context (BUG-01 fix) ─────────────────────────
        history_ctx = self.session_store.get_context_for_agent("personal", limit=10)

        # ── Thinking phase ────────────────────────────────────────────────────
        thinking_trace = ""
        if THINKING_ENABLED:
            yield OrchestratorEvent(type="thinking", message="Analyzing…")
            try:
                thinking_trace = self._build_thinking_trace(query)
                if thinking_trace:
                    yield OrchestratorEvent(type="thinking", message=thinking_trace)
            except Exception as e:
                from lirox.utils.structured_logger import get_logger
                get_logger("lirox.orchestrator").warning(f"Thinking error: {e}")

        # ── Direct chat handled by Mind Agent (v4) ───────────────────────────
        if not self._needs_agent(query):
            agent       = self._get_mind_agent()
            agent_name  = "mind"

            # Build system prompt with conversation history (BUG-01 fix)
            mind_system = system_prompt
            if history_ctx:
                mind_system = (
                    f"{system_prompt}\n\nCONVERSATION HISTORY:\n{history_ctx}"
                    if system_prompt else
                    f"CONVERSATION HISTORY:\n{history_ctx}"
                )

            result_text = ""
            try:
                for event in agent.run(
                    query,
                    system_prompt=mind_system,
                    context=thinking_trace,
                    mode="advisor",
                ):
                    yield OrchestratorEvent(
                        type    = event.get("type", "agent_progress"),
                        agent   = agent_name,
                        message = event.get("message", ""),
                        data    = event,
                    )
                    if event.get("type") == "done":
                        result_text = event.get("answer", event.get("message", ""))
            except Exception as e:
                yield OrchestratorEvent(type="error", message=str(e))
                result_text = f"Error: {e}"

            self.global_memory.save_exchange(query, result_text)
            session.add("assistant", result_text, agent=agent_name, mode="complex")
            self.session_store.save_current()

            yield OrchestratorEvent(
                type    = "done",
                agent   = agent_name,
                message = result_text,
                data    = {"total_time": time.time() - start, "mode": "complex"},
            )
            return

        # ── Personal agent tool-use path ──────────────────────────────────────

        complex_ctx = thinking_trace
        if complex_ctx:
            complex_ctx += COMPLEX_FORMAT_SUFFIX
        else:
            complex_ctx = COMPLEX_FORMAT_SUFFIX.strip()

        # Include conversation history in context (BUG-01 fix)
        if history_ctx:
            complex_ctx = f"CONVERSATION HISTORY:\n{history_ctx}\n\n{complex_ctx}"

        # Build system prompt with conversation history (BUG-01 fix)
        personal_system = system_prompt
        if history_ctx and not system_prompt:
            personal_system = ""

        agent       = self._get_personal_agent()
        result_text = ""

        try:
            for event in agent.run(
                query,
                system_prompt=personal_system,
                context=complex_ctx,
                mode="complex",
            ):
                yield OrchestratorEvent(
                    type    = event.get("type", "agent_progress"),
                    agent   = "personal",
                    message = event.get("message", ""),
                    data    = event,
                )
                if event.get("type") == "done":
                    result_text = event.get("answer", event.get("message", ""))
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent="personal", mode="complex")
        self.session_store.save_current()

        yield OrchestratorEvent(
            type    = "done",
            agent   = "personal",
            message = result_text,
            data    = {"total_time": time.time() - start, "mode": "complex"},
        )

    # ── Kept for UI compat ────────────────────────────────────────────────────

    def set_agent(self, agent_name: str) -> bool:
        # In v3, there's only one agent. This is a no-op but returns True
        # so existing callers don't break.
        return True
