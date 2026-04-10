"""Lirox v1.0.0 — Master Orchestrator"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, Optional

from lirox.config import THINKING_ENABLED
from lirox.memory.manager import MemoryManager
from lirox.memory.session_store import SessionStore
from lirox.thinking.scratchpad import Scratchpad


class AgentType(Enum):
    PERSONAL = "personal"
    MIND     = "mind"


@dataclass
class OrchestratorEvent:
    type:      str
    agent:     str = ""
    message:   str = ""
    data:      Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MasterOrchestrator:
    def __init__(self, profile_data: Dict[str, Any] = None):
        self.profile_data    = profile_data or {}
        self.global_memory   = MemoryManager()
        self.memory          = self.global_memory
        self.session_store   = SessionStore()
        self._agent:         Optional[Any] = None
        self._mind_agent:    Optional[Any] = None   # FIX: declared in __init__
        self._agent_memory:  Dict[AgentType, MemoryManager] = {}
        self._agent_scratch: Dict[AgentType, Scratchpad]    = {}

    def _get_personal_agent(self):
        if self._agent is None:
            if AgentType.PERSONAL not in self._agent_memory:
                self._agent_memory[AgentType.PERSONAL] = MemoryManager(agent_name="personal")
            if AgentType.PERSONAL not in self._agent_scratch:
                self._agent_scratch[AgentType.PERSONAL] = Scratchpad()
            from lirox.agents.personal_agent import PersonalAgent
            self._agent = PersonalAgent(
                memory=self._agent_memory[AgentType.PERSONAL],
                scratchpad=self._agent_scratch[AgentType.PERSONAL],
                profile_data=self.profile_data)
        return self._agent

    def _get_mind_agent(self):
        if self._mind_agent is None:
            if AgentType.MIND not in self._agent_memory:
                self._agent_memory[AgentType.MIND] = MemoryManager(agent_name="mind")
            if AgentType.MIND not in self._agent_scratch:
                self._agent_scratch[AgentType.MIND] = Scratchpad()
            from lirox.mind.agent import MindAgent
            self._mind_agent = MindAgent(
                memory=self._agent_memory[AgentType.MIND],
                scratchpad=self._agent_scratch[AgentType.MIND],
                profile_data=self.profile_data)
        return self._mind_agent

    def _get_identity_prompt(self) -> str:
        try:
            from lirox.mind.agent import get_soul, get_learnings
            return get_soul().to_system_prompt(get_learnings().to_context_string())
        except Exception:
            return "You are Lirox, an autonomous personal AI agent."

    def _build_thinking_trace(self, query: str) -> str:
        context = self.global_memory.get_relevant_context(query)
        try:
            from lirox.thinking.chain_of_thought import ThinkingEngine
            return ThinkingEngine().reason(query, context)
        except Exception:
            return ""

    def _needs_agent(self, query: str) -> bool:
        q = query.lower()
        signals = [
            "open", "click", "launch", "run", "execute", "create", "write",
            "read", "delete", "search", "find", "list files", "screenshot",
            "install", "download", "build", "navigate", "browse", "fetch",
            "git ", "python ", "docker", "make a", "make me", "generate",
            "folder", "directory", "file", "code", "script", "program",
            "pdf", "csv", "json", ".txt", "in my ", "in the ", "save to",
            "store", "add to", "add details", "write to",
        ]
        return any(s in q for s in signals)

    def run(self, query: str, system_prompt: str = "",
            mode: str = None, agent_override: str = None
            ) -> Generator[OrchestratorEvent, None, None]:
        start   = time.time()
        session = self.session_store.current()
        session.add("user", query, agent="personal", mode="complex")
        history_ctx = self.session_store.get_context_for_agent("personal", limit=10)

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

        if not self._needs_agent(query):
            agent      = self._get_mind_agent()
            agent_name = "mind"
            mind_sys   = (f"{system_prompt}\n\nCONVERSATION HISTORY:\n{history_ctx}"
                          if history_ctx and system_prompt else
                          f"CONVERSATION HISTORY:\n{history_ctx}" if history_ctx else system_prompt)
            result_text = ""
            try:
                for event in agent.run(query, system_prompt=mind_sys,
                                       context=thinking_trace, mode="advisor"):
                    yield OrchestratorEvent(type=event.get("type", "agent_progress"),
                                             agent=agent_name, message=event.get("message", ""),
                                             data=event)
                    if event.get("type") == "done":
                        result_text = event.get("answer", event.get("message", ""))
            except Exception as e:
                yield OrchestratorEvent(type="error", message=str(e))
                result_text = f"Error: {e}"
            self.global_memory.save_exchange(query, result_text)
            session.add("assistant", result_text, agent=agent_name, mode="complex")
            self.session_store.save_current()
            yield OrchestratorEvent(type="done", agent=agent_name, message=result_text,
                                     data={"total_time": time.time() - start})
            return

        complex_ctx = thinking_trace or ""
        if history_ctx:
            complex_ctx = f"CONVERSATION HISTORY:\n{history_ctx}\n\n{complex_ctx}"

        agent       = self._get_personal_agent()
        result_text = ""
        try:
            for event in agent.run(query, system_prompt=system_prompt,
                                   context=complex_ctx, mode="complex"):
                yield OrchestratorEvent(type=event.get("type", "agent_progress"),
                                         agent="personal", message=event.get("message", ""),
                                         data=event)
                if event.get("type") == "done":
                    result_text = event.get("answer", event.get("message", ""))
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent="personal", mode="complex")
        self.session_store.save_current()
        yield OrchestratorEvent(type="done", agent="personal", message=result_text,
                                 data={"total_time": time.time() - start})
