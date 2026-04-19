"""Lirox v1.1 — Master Orchestrator"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

from lirox.config import THINKING_ENABLED
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
        # Single shared memory — both orchestrator and agent use the same instance
        self.global_memory   = MemoryManager()
        self.session_store   = SessionStore()
        self._agent:         Optional[Any] = None
        self._interaction_count: int = 0

    def _get_agent(self):
        if self._agent is None:
            from lirox.agents.personal_agent import PersonalAgent
            self._agent = PersonalAgent(
                memory=self.global_memory,
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

    @staticmethod
    def _is_complex_query(query: str) -> bool:
        """Return True when the query benefits from deep multi-phase reasoning."""
        signals = [
            "how should", "what is the best", "compare", "why does", "design",
            "architect", "trade-off", "pros and cons", "evaluate", "which approach",
            "recommend", "strategy", "plan", "explain", "analyse", "analyze",
            "reasoning", "think through", "help me understand", "walk me through",
            "break down",
        ]
        q = query.lower()
        return any(s in q for s in signals) or len(query) > 200

    @staticmethod
    def _needs_agent(query: str) -> bool:
        """Return True when the query requires tool-using agent capabilities."""
        signals = [
            "open", "click", "launch", "run", "execute", "create", "write",
            "read", "delete", "search", "find", "list files", "screenshot",
            "install", "download", "build", "navigate", "browse", "fetch",
            "git ", "python ", "docker", "make a", "make me", "generate",
            "folder", "directory", "file", "code", "script", "program",
            "pdf", "csv", "json", ".txt", "in my ", "in the ", "save to",
            "store", "add to", "add details", "write to",
        ]
        return any(s in query.lower() for s in signals)

    def _run_thinking(self, query: str, context: str) -> Generator[OrchestratorEvent, None, None]:
        """Run the 8-phase thinking engine and yield OrchestratorEvents.

        Yields:
            - One ``thinking_phase`` event per reasoning phase.
            - One ``thinking_done`` event with the full trace text.
        Returns the trace string via the ``thinking_done`` event's data.
        """
        try:
            from lirox.mind.thinking_engine import ThinkingEngine
            engine = ThinkingEngine()
            for evt in engine.reason(query, context):
                if evt["type"] == "thinking_phase":
                    yield OrchestratorEvent(
                        type="thinking_phase",
                        message=evt.get("phase_name", ""),
                        data=evt,
                    )
                elif evt["type"] == "thinking_done":
                    yield OrchestratorEvent(
                        type="thinking_done",
                        message=evt.get("trace", ""),
                        data=evt,
                    )
        except Exception as e:
            # Thinking failure must never block the main query
            yield OrchestratorEvent(type="thinking_done", message="", data={})

    def run(self, query: str) -> Generator[OrchestratorEvent, None, None]:
        start = time.time()
        self._interaction_count += 1
        session = self.session_store.current()
        session.add("user", query, agent="personal")

        history_ctx = self._get_recent_context(limit=3)
        context = f"RECENT CONTEXT:\n{history_ctx}" if history_ctx else ""

        # ── Thinking phase ────────────────────────────────────────────────────
        thinking_trace = ""
        if THINKING_ENABLED:
            # Emit initial spinner hint
            yield OrchestratorEvent(type="thinking", message="Analyzing…")
            for evt in self._run_thinking(query, context):
                if evt.type == "thinking_done":
                    thinking_trace = evt.message
                else:
                    yield evt

        # ── Agent execution ───────────────────────────────────────────────────
        full_context = context
        if thinking_trace:
            full_context = (
                f"{context}\n\n{thinking_trace}" if context else thinking_trace
            )

        agent = self._get_agent()
        result_text = ""
        try:
            for event in agent.run(query, context=full_context):
                event_type = event.get("type", "agent_progress")
                if event_type == "done":
                    result_text = event.get("answer", event.get("message", ""))
                else:
                    yield OrchestratorEvent(
                        type=event_type, agent="personal",
                        message=event.get("message", ""), data=event)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        # Save exchange once (agent no longer saves separately)
        self.global_memory.save_exchange(query, result_text)
        session.add("assistant", result_text, agent="personal")
        self.session_store.save_current()
        yield OrchestratorEvent(
            type="done", agent="personal", message=result_text,
            data={"total_time": time.time() - start})

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
