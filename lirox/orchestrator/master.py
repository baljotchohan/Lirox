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
        self._interaction_count: int = 0  # BUG-C3 FIX: track interactions for auto-training
        # Permission system — optional; initialised lazily on first use
        self._permission_system: Optional[Any] = None
        # BUG-H1 FIX: restore last session into memory buffer on startup
        self._restore_last_session()

    def _restore_last_session(self) -> None:
        """
        Restore session metadata only — NOT conversation content.

        Loading raw conversation turns causes context bleed where the agent
        responds to old topics when the user starts fresh. Instead we only
        restore the session record so /history and /session commands work,
        and build a compact summary available on explicit request.
        """
        try:
            sessions = self.session_store.list_sessions(limit=1)
            if not sessions:
                return
            last = sessions[0]
            # Restore the session identity but NOT its conversation content
            # into the live buffer. The content stays on disk and is only
            # surfaced when the user explicitly asks about past conversations.
            self.session_store.set_current(last)
        except Exception:
            pass  # startup must never fail due to session restoration

    def _get_recent_context_summary(self, limit: int = 3) -> str:
        """
        Build a compact 1-3 exchange summary from the current session ONLY.
        Used to give the agent awareness of what was just discussed without
        contaminating fresh conversations.
        Returns empty string for first message in a session.
        """
        try:
            session = self.session_store.current()
            # Only include entries from THIS session run (after startup)
            recent = [e for e in session.entries if e.role in ("user", "assistant")]
            # Don't include the just-added user message (last entry)
            recent = recent[:-1]
            if not recent:
                return ""
            # Take the last `limit` exchanges
            pairs = recent[-(limit * 2):]
            lines = []
            for e in pairs:
                label = "User" if e.role == "user" else "Assistant"
                lines.append(f"{label}: {e.content[:300]}")
            return "\n".join(lines)
        except Exception:
            return ""

    @property
    def permission_system(self):
        """Return (and lazily initialise) the shared PermissionSystem."""
        if self._permission_system is None:
            try:
                from lirox.autonomy.permission_system import PermissionSystem
                self._permission_system = PermissionSystem()
            except Exception:
                pass
        return self._permission_system

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

    def _build_thinking_trace(self, query: str) -> str:
        context = self.global_memory.get_relevant_context(query)
        try:
            # Use AdvancedReasoning for complex queries (multi-path with scored approaches)
            if self._is_complex_query(query):
                from lirox.thinking.advanced_reasoning import AdvancedReasoning
                return AdvancedReasoning().reason_deep(query)
            from lirox.thinking.chain_of_thought import ThinkingEngine
            return ThinkingEngine().reason(query, context)
        except Exception:
            return ""

    @staticmethod
    def _is_complex_query(query: str) -> bool:
        """Return True when the query is likely to benefit from deep multi-path reasoning."""
        complex_signals = [
            "how should", "what is the best", "compare", "why does", "design",
            "architect", "trade-off", "trade off", "pros and cons", "evaluate",
            "which approach", "recommend", "strategy", "plan", "explain",
            "analyse", "analyze", "reasoning", "think through",
        ]
        q = query.lower()
        return any(s in q for s in complex_signals) or len(query) > 200

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
        self._interaction_count += 1
        session = self.session_store.current()
        session.add("user", query, agent="personal", mode="complex")

        # Only use context from THIS session's recent turns (not previous sessions)
        # This prevents context bleed from previous restarts/conversations
        history_ctx = self._get_recent_context_summary(limit=3)

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
            # Only inject history if we actually have some from this session
            if history_ctx:
                mind_sys = f"RECENT CONTEXT (this session only):\n{history_ctx}"
                if system_prompt:
                    mind_sys = f"{system_prompt}\n\n{mind_sys}"
            else:
                mind_sys = system_prompt or ""
            result_text = ""
            try:
                for event in agent.run(query, system_prompt=mind_sys,
                                       context=thinking_trace, mode="advisor"):
                    event_type = event.get("type", "agent_progress")
                    if event_type == "done":
                        result_text = event.get("answer", event.get("message", ""))
                    else:
                        yield OrchestratorEvent(type=event_type,
                                                 agent=agent_name, message=event.get("message", ""),
                                                 data=event)
            except Exception as e:
                yield OrchestratorEvent(type="error", message=str(e))
                result_text = f"Error: {e}"
            self.global_memory.save_exchange(query, result_text)
            session.add("assistant", result_text, agent=agent_name, mode="complex")
            self.session_store.save_current()
            yield OrchestratorEvent(type="done", agent=agent_name, message=result_text,
                                     data={"total_time": time.time() - start})
            if self._interaction_count % 20 == 0:
                self._auto_train()
            return

        # Personal agent path — only inject recent context, not full history
        complex_ctx = thinking_trace or ""
        if history_ctx:
            complex_ctx = f"RECENT CONTEXT:\n{history_ctx}\n\n{complex_ctx}" if complex_ctx else f"RECENT CONTEXT:\n{history_ctx}"

        agent       = self._get_personal_agent()
        result_text = ""
        try:
            for event in agent.run(query, system_prompt=system_prompt,
                                   context=complex_ctx, mode="complex"):
                event_type = event.get("type", "agent_progress")
                if event_type == "done":
                    # Capture result; orchestrator emits its own "done" below
                    result_text = event.get("answer", event.get("message", ""))
                else:
                    yield OrchestratorEvent(type=event_type,
                                             agent="personal", message=event.get("message", ""),
                                             data=event)
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent="personal", mode="complex")
        self.session_store.save_current()
        yield OrchestratorEvent(type="done", agent="personal", message=result_text,
                                 data={"total_time": time.time() - start})
        # BUG-C3 FIX: auto-train every 20 interactions (non-blocking)
        if self._interaction_count % 20 == 0:
            self._auto_train()   # non-blocking — fires background thread

    def _auto_train(self) -> None:
        """
        Automatically extract learnings every 20 interactions.
        Runs in a daemon background thread — never blocks the REPL.
        """
        import threading

        def _train_worker():
            try:
                from lirox.mind.agent import get_trainer
                stats = get_trainer(self.global_memory).train(
                    self.global_memory, self.session_store
                )
                facts_added = stats.get("facts_added", 0)
                if facts_added > 0:
                    # Can't yield from a thread; log to structured logger instead.
                    from lirox.utils.structured_logger import get_logger
                    get_logger("lirox.auto_train").info(
                        f"Auto-trained: {facts_added} new fact(s)"
                    )
            except Exception:
                pass  # auto-training is always best-effort

        t = threading.Thread(target=_train_worker, daemon=True, name="lirox-auto-train")
        t.start()
