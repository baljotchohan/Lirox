"""Lirox v2.0.0 — Background Engine

Daemon thread that auto-trains every 15 messages.
Extracts facts, topics, projects, and communication style from conversation history.

BUG-5 FIX: Background auto-training runs every 15 messages (not 20 or never).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

from lirox.config import DATA_DIR

_log_path = os.path.join(DATA_DIR, "improvements.log")
logger    = logging.getLogger("lirox.background")


def _log(msg: str) -> None:
    """Append a timestamped line to the improvements log (silent, no console output)."""
    try:
        with open(_log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


class BackgroundEngine:
    """
    Daemon thread that monitors message count and auto-trains every 15 messages.
    Training extracts persistent knowledge from recent conversation exchanges.
    """

    TRAIN_INTERVAL = 15  # auto-train every N messages

    def __init__(self, memory_manager=None, learnings_store=None):
        self._memory   = memory_manager
        self._learnings = learnings_store
        self._msg_count = 0
        self._lock      = threading.Lock()
        self._running   = False
        self._thread: Optional[threading.Thread] = None

    def set_stores(self, memory_manager, learnings_store) -> None:
        """Inject stores after init (useful when agent initializes them)."""
        with self._lock:
            self._memory    = memory_manager
            self._learnings = learnings_store

    def start(self) -> None:
        """Start the background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, daemon=True, name="lirox-background"
        )
        self._thread.start()
        _log("BackgroundEngine started")

    def stop(self) -> None:
        self._running = False

    def tick(self) -> None:
        """Call after each user message. Triggers training at every TRAIN_INTERVAL."""
        with self._lock:
            self._msg_count += 1
            count = self._msg_count
        if count % self.TRAIN_INTERVAL == 0:
            t = threading.Thread(
                target=self._auto_train, daemon=True, name="lirox-train"
            )
            t.start()

    def _run(self) -> None:
        """Background loop — currently lightweight; training is event-driven via tick()."""
        while self._running:
            time.sleep(60)  # heartbeat

    def _auto_train(self) -> None:
        """Extract knowledge from recent conversation history and persist it."""
        if self._memory is None or self._learnings is None:
            return
        try:
            conversation = self._memory.format_for_training(n=50)
            if not conversation.strip():
                return

            from lirox.utils.llm import generate_response

            prompt = (
                "Analyze this conversation and extract user knowledge as JSON.\n"
                "Return ONLY valid JSON with these keys:\n"
                '{\n'
                '  "facts": ["fact1", "fact2"],\n'
                '  "topics": ["topic1"],\n'
                '  "projects": ["project1"],\n'
                '  "communication_style": {"tone": "direct", "format": "concise"}\n'
                '}\n\n'
                f"Conversation:\n{conversation[:6000]}"
            )
            raw = generate_response(prompt)
            if not raw or "Error:" in raw[:20]:
                return

            # Parse JSON from response
            from lirox.utils.llm import strip_code_fences
            raw = strip_code_fences(raw, "json")
            try:
                extracted = json.loads(raw)
            except json.JSONDecodeError:
                # Try to find JSON block in response
                import re
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if not m:
                    return
                extracted = json.loads(m.group(0))

            counts = self._learnings.merge_extracted(extracted)
            _log(
                f"Auto-train complete: +{counts['facts']} facts, "
                f"+{counts['topics']} topics, +{counts['projects']} projects"
            )
        except Exception as e:
            _log(f"Auto-train error: {e}")

    def manual_train(self) -> dict:
        """Run training immediately and return results. Used by /train command."""
        if self._memory is None or self._learnings is None:
            return {"error": "Stores not initialized"}
        try:
            conversation = self._memory.format_for_training(n=100)
            if not conversation.strip():
                return {"message": "No conversation history to train from."}

            from lirox.utils.llm import generate_response, strip_code_fences
            import re

            prompt = (
                "Analyze this conversation and extract user knowledge as JSON.\n"
                "Return ONLY valid JSON with these keys:\n"
                '{\n'
                '  "facts": ["fact1", "fact2"],\n'
                '  "topics": ["topic1"],\n'
                '  "projects": ["project1"],\n'
                '  "communication_style": {"tone": "direct", "format": "concise"}\n'
                '}\n\n'
                f"Conversation:\n{conversation[:8000]}"
            )
            raw = generate_response(prompt)
            if not raw or "Error:" in raw[:20]:
                return {"error": raw}

            raw = strip_code_fences(raw, "json")
            try:
                extracted = json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if not m:
                    return {"error": "Could not parse LLM response as JSON"}
                extracted = json.loads(m.group(0))

            counts = self._learnings.merge_extracted(extracted)
            _log(
                f"Manual train complete: +{counts['facts']} facts, "
                f"+{counts['topics']} topics, +{counts['projects']} projects"
            )
            return {"success": True, **counts}
        except Exception as e:
            return {"error": str(e)}
