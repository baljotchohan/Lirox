"""Lirox V1 — Auto-Learning Background Thread.

Automatically extracts learnings from conversations in the background every
AUTO_TRAIN_INTERVAL_MINUTES (default 30) without blocking user interaction.

Features:
  - Runs as a daemon thread (cleaned up automatically on exit)
  - Configurable interval via AUTO_TRAIN_INTERVAL_MINUTES env var
  - Tracks conversation count; trains after every N new messages
  - Silent operation — no console spam unless verbose mode is active
  - Safe shutdown via stop()

Usage:
    from lirox.autonomy.auto_learner import AutoLearner

    learner = AutoLearner(memory_manager, session_store)
    learner.start()      # starts background thread
    # ... application runs ...
    learner.stop()       # graceful shutdown
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Optional

_log = logging.getLogger("lirox.auto_learner")

# Config
_DEFAULT_INTERVAL_MINUTES = 30
_TRAIN_AFTER_N_MESSAGES   = int(os.getenv("AUTO_TRAIN_AFTER_MESSAGES", "10"))
_TRAIN_INTERVAL_SECONDS   = int(
    os.getenv("AUTO_TRAIN_INTERVAL_MINUTES", str(_DEFAULT_INTERVAL_MINUTES))
) * 60
_ENABLED = os.getenv("AUTO_TRAIN_ENABLED", "true").lower() != "false"


class AutoLearner:
    """Background training thread — trains silently at configurable intervals."""

    def __init__(
        self,
        memory_manager,
        session_store,
        on_train_complete: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """
        Args:
            memory_manager: The global MemoryManager instance.
            session_store:  The SessionStore instance.
            on_train_complete: Optional callback called with training stats dict
                               when training finishes. Can be used to emit an
                               ``auto_train`` event to the UI.
        """
        self._memory   = memory_manager
        self._sessions = session_store
        self._callback = on_train_complete
        self._stop_evt = threading.Event()
        self._thread:  Optional[threading.Thread] = None
        self._last_message_count  = 0
        self._last_trained_count  = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background training thread (idempotent)."""
        if not _ENABLED:
            return
        if self._thread and self._thread.is_alive():
            return  # already running
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="lirox-auto-learner",
            daemon=True,  # dies with the main process automatically
        )
        self._thread.start()
        _log.debug("AutoLearner started (interval=%ds, after=%d msgs)",
                   _TRAIN_INTERVAL_SECONDS, _TRAIN_AFTER_N_MESSAGES)

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it."""
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def notify_new_message(self) -> None:
        """Called after each user message to track conversation count."""
        self._last_message_count += 1
        # Trigger immediately if we've hit the message threshold
        if (self._last_message_count - self._last_trained_count) >= _TRAIN_AFTER_N_MESSAGES:
            self._do_train()

    def train_now(self) -> dict:
        """Run training synchronously and return stats (for testing)."""
        return self._do_train()

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Main loop: sleep for interval, then train."""
        while not self._stop_evt.wait(timeout=_TRAIN_INTERVAL_SECONDS):
            self._do_train()

    def _do_train(self) -> dict:
        """Execute training and call the callback if set."""
        stats: dict = {}
        try:
            from lirox.mind.agent import get_trainer
            trainer = get_trainer()
            stats   = trainer.train(self._memory, self._sessions)
            self._last_trained_count = self._last_message_count

            # Only fire callback if something was actually learned
            facts = stats.get("facts_added", 0)
            if facts > 0 and self._callback:
                try:
                    self._callback(stats)
                except Exception:
                    pass

            _log.debug("AutoLearner trained: %s", stats)
        except Exception as e:
            _log.debug("AutoLearner train error: %s", e)
        return stats

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def message_count(self) -> int:
        return self._last_message_count

    @property
    def messages_since_last_train(self) -> int:
        return self._last_message_count - self._last_trained_count
