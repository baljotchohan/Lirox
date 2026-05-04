"""Lirox v1.1 — Master Orchestrator"""
from __future__ import annotations
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

from lirox.config import THINKING_ENABLED
from lirox.memory.manager import MemoryManager
from lirox.memory.session_store import SessionStore

_logger = logging.getLogger("lirox.orchestrator")


@dataclass
class OrchestratorEvent:
    type:      str
    agent:     str = ""
    message:   str = ""
    data:      Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


CONTINUATION_TOKENS = {"ok", "yes", "continue", "proceed", "do it", "go ahead", "sure", "ok continue"}

@dataclass
class PendingAction:
    agent: str
    action_type: str
    context: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

class MasterOrchestrator:
    def __init__(self, profile_data: Dict[str, Any] = None):
        self.profile_data    = profile_data or {}
        # Single shared memory — both orchestrator and agent use the same instance
        self.global_memory   = MemoryManager()
        self.session_store   = SessionStore()
        self._agent:         Optional[Any] = None
        self._rag_retriever: Optional[Any] = None
        self._interaction_count: int = 0
        self.pending_action: Optional[PendingAction] = None

    def _get_agent(self):
        if self._agent is None:
            from lirox.agents.personal_agent import PersonalAgent
            self._agent = PersonalAgent(
                memory=self.global_memory,
                profile_data=self.profile_data)
        return self._agent

    def _get_rag_retriever(self):
        """Lazy-init RAG retriever so import cost is paid only when needed."""
        if self._rag_retriever is None:
            try:
                from lirox.rag.retriever import RAGRetriever
                self._rag_retriever = RAGRetriever()
            except Exception as e:
                _logger.warning("RAG retriever unavailable: %s", e)
                self._rag_retriever = False  # sentinel: don't retry
        return self._rag_retriever if self._rag_retriever is not False else None

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



    def run(self, query: str) -> Generator[OrchestratorEvent, None, None]:
        start = time.time()
        self._interaction_count += 1

        # ── Pending action handling ─────────────────────────────────────────
        # If the previous response promised an action and the user just said
        # "ok"/"continue"/"yes", execute the previously promised action instead
        # of running classification again from scratch.
        q_norm = query.strip().lower().rstrip("!.?")
        if self.pending_action and q_norm in CONTINUATION_TOKENS:
            original = self.pending_action.context.get("original_query", query)
            self.pending_action = None  # one-shot; consume it
            yield OrchestratorEvent(
                type="info", message=f"Continuing previous task: {original[:60]}…"
            )
            # Re-enter run() with the original promised query
            yield from self.run(original)
            return
        # ────────────────────────────────────────────────────────────────────

        session = self.session_store.current()
        session.add("user", query, agent="personal")

        # Skip context injection for very short queries (greetings) to prevent
        # hallucination about past conversations.
        if len(query.split()) > 3:
            history_ctx = self._get_recent_context(limit=3)
            context = f"RECENT CONTEXT:\n{history_ctx}" if history_ctx else ""
        else:
            context = ""

        # ── Agent execution ───────────────────────────────────────────────────
        full_context = context

        # Inject RAG context only for queries that are document/knowledge-related.
        # Unconditional injection bloats every prompt and misleads the LLM for
        # pure conversational queries.
        _RAG_TRIGGERS = (
            "my files", "my docs", "my documents", "in my folder",
            "in my knowledge", "from my notes", "uploaded", "indexed",
            "what does", "what did", "what is in", "summarise", "summarize",
            "find in", "search my", "according to", "based on my",
        )
        q_lower_rag = query.lower()
        _should_inject_rag = any(t in q_lower_rag for t in _RAG_TRIGGERS)

        try:
            rag = self._get_rag_retriever()
            if rag and not rag.is_empty and _should_inject_rag:
                rag_ctx = rag.retrieve(query, n_results=5)
                if rag_ctx:
                    full_context = f"{full_context}\n\n{rag_ctx}" if full_context else rag_ctx
        except Exception as e:
            _logger.debug("RAG retrieval skipped: %s", e)
        agent = self._get_agent()
        result_text = ""
        last_thinking_result = None
        try:
            for event in agent.run(query, context=full_context):
                event_type = event.get("type", "agent_progress")
                if event_type == "done":
                    result_text = event.get("answer", event.get("message", ""))
                    # Capture thinking result if agent included it
                    if "thinking_result" in event:
                        last_thinking_result = event["thinking_result"]
                else:
                    # Capture thinking done events from the engine
                    if event_type == "thinking_done" or (event.get("data") and isinstance(event.get("data"), dict)):
                        thinking_data = event.get("data", {})
                        if isinstance(thinking_data, dict) and "agent_views" in thinking_data:
                            last_thinking_result = thinking_data
                    yield OrchestratorEvent(
                        type=event_type, agent=event.get("agent", "personal"),
                        message=event.get("message", ""), data=event)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            yield OrchestratorEvent(type="error", message=str(e))
            result_text = f"Error: {e}"

        # Save exchange once (agent no longer saves separately).
        # Each persistence step is independent so a failure in one does not
        # prevent the others from running (partial-failure resilience).
        try:
            self.global_memory.save_exchange(query, result_text)
        except Exception as e:
            _logger.warning("Memory save_exchange failed: %s", e)
        try:
            session.add("assistant", result_text, agent="personal")
        except Exception as e:
            _logger.warning("Session.add failed: %s", e)
        try:
            self.session_store.save_current()
        except Exception as e:
            _logger.warning("session_store.save_current failed: %s", e)

        done_data = {"total_time": time.time() - start}
        if last_thinking_result:
            done_data["thinking_result"] = last_thinking_result

        # ── Capture promised future action so "ok continue" works ──────────────
        # Match explicit first-person action promises (including "let me <verb>")
        # but NOT passive phrases like "I can help" or "let me know" that would
        # mis-trigger re-execution on the next short acknowledgement.
        import re as _re
        _ACTION_VERBS = (
            r"create|generate|build|write|make|set up|put together|draft|prepare"
        )
        PROMISE_RE = _re.compile(
            r"\b(I'?ll|I will go ahead and|I'?m going to"
            r"|let me go ahead and"
            rf"|let me (?:{_ACTION_VERBS}))\s*"
            rf"(?:{_ACTION_VERBS})?\b",
            _re.IGNORECASE,
        )
        if result_text and PROMISE_RE.search(result_text):
            self.pending_action = PendingAction(
                agent="personal",
                action_type="execute_promise",
                context={"original_query": query, "promise_text": result_text[:500]},
            )
        else:
            # Clear stale pending action if a new turn produced a real result
            if self.pending_action and result_text:
                self.pending_action = None
        # ───────────────────────────────────────────────────────────────────────

        yield OrchestratorEvent(
            type="done", agent="personal", message=result_text,
            data=done_data)

        if self._interaction_count % 5 == 0:
            self._auto_train()

    def _auto_train(self) -> None:
        import threading
        def _worker():
            try:
                from lirox.memory.trainer import TrainingEngine
                from lirox.memory.learnings import LearningsStore
                learnings = LearningsStore()
                TrainingEngine(learnings).train(self.global_memory, self.session_store)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True, name="lirox-auto-train").start()
