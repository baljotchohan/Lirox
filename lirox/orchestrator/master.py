"""Lirox v3.0 — Master Orchestrator (Clean)"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

from lirox.memory.manager import MemoryManager
from lirox.memory.session_store import SessionStore


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
        self.session_store   = SessionStore()
        self._agent:         Optional[Any] = None
        self._interaction_count: int = 0
        self.default_provider = None

    def _get_agent(self):
        if self._agent is None:
            from lirox.agents.personal_agent import PersonalAgent
            self._agent = PersonalAgent(
                memory=MemoryManager(agent_name="personal"),
                profile_data=self.profile_data)
        return self._agent

    def _get_recent_context(self, limit: int = 3) -> str:
        try:
            session = self.session_store.current()
            entries = [e for e in session.entries if e.role in ("user", "assistant")]
            if entries and entries[-1].role == "user":
                entries = entries[:-1]
            if not entries:
                return ""
            tail = entries[-(limit * 2):]
            return "\n".join(
                f"{'User' if e.role == 'user' else 'Assistant'}: {e.content[:300]}"
                for e in tail
            )
        except Exception:
            return ""

    def run(self, query: str) -> Generator[OrchestratorEvent, None, None]:
        start = time.time()
        self._interaction_count += 1
        session = self.session_store.current()
        session.add("user", query, agent="personal")

        history_ctx = self._get_recent_context(limit=3)
        context = f"RECENT CONTEXT:\n{history_ctx}" if history_ctx else ""

        yield OrchestratorEvent(type="thinking", message="Analyzing…")

        agent = self._get_agent()
        result_text = ""
        try:
            for event in agent.run(query, context=context):
                event_type = event.get("type", "agent_progress")
                if event_type == "done":
                    result_text = event.get("answer", event.get("message", ""))
                else:
                    yield OrchestratorEvent(
                        type=event_type, agent="personal",
                        message=event.get("message", ""), data=event)
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent="personal")
        self.session_store.save_current()
        yield OrchestratorEvent(
            type="done", agent="personal", message=result_text,
            data={"total_time": time.time() - start})

        # Auto-train every 20 interactions
        if self._interaction_count % 20 == 0:
            self._auto_train()

    def _auto_train(self) -> None:
        import threading
        def _worker():
            try:
                from lirox.mind.trainer import TrainingEngine
                from lirox.mind.learnings import LearningsStore
                learnings = LearningsStore()
                TrainingEngine(learnings).train(self.global_memory, self.session_store)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True, name="lirox-auto-train").start()
