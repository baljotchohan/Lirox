"""Lirox v3.0 — Master Orchestrator (Single Agent Architecture)"""
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
    CHAT     = "chat"   # direct LLM, no agent overhead for simple queries


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

    # ── Helper ────────────────────────────────────────────────────────────────

    def _get_identity_prompt(self) -> str:
        try:
            from lirox.soul import get_identity_prompt
            return get_identity_prompt()
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
        True if the query requires tool use (desktop, file, shell, web).
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

        # ── Direct chat (no tool use needed) ─────────────────────────────────
        if not self._needs_agent(query):
            yield OrchestratorEvent(type="agent_start", agent="personal",
                                    message="Answering directly")
            try:
                from lirox.utils.llm import generate_response
                identity = self._get_identity_prompt()
                prompt   = query
                if thinking_trace:
                    prompt = f"Thinking:\n{thinking_trace}\n\nUser: {query}"
                answer = generate_response(
                    prompt, provider="auto",
                    system_prompt=identity + COMPLEX_FORMAT_SUFFIX,
                )
                self.global_memory.save_exchange(query, answer)
                session.add("assistant", answer, agent="personal", mode="complex")
                self.session_store.save_current()
                yield OrchestratorEvent(
                    type="done", agent="personal", message=answer,
                    data={"total_time": time.time() - start},
                )
            except Exception as e:
                yield OrchestratorEvent(type="error", message=str(e))
            return

        # ── Personal agent tool-use path ──────────────────────────────────────
        yield OrchestratorEvent(type="agent_start", agent="personal",
                                message="Personal agent activated")

        complex_ctx = thinking_trace
        if complex_ctx:
            complex_ctx += COMPLEX_FORMAT_SUFFIX
        else:
            complex_ctx = COMPLEX_FORMAT_SUFFIX.strip()

        agent       = self._get_personal_agent()
        result_text = ""

        try:
            for event in agent.run(
                query,
                system_prompt=system_prompt,
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
