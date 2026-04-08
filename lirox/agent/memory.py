"""
Lirox v2.0 — Agent Memory

Persistent conversation memory with search and stats.
Stores messages with role/content, supports keyword search.
"""

from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Optional


class Memory:
    """
    Simple persistent memory for an agent.

    Stores messages as {role, content} dicts.  Supports search and stats.
    """

    def __init__(self, storage_file: str = "memory.json", max_messages: int = 200):
        self.storage_file = storage_file
        self.max_messages = max_messages
        self.history: List[Dict[str, str]] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.history = data
            except Exception:
                self.history = []

    def _save(self) -> None:
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # Storage is best-effort

    # ── Core API ──────────────────────────────────────────────────────────────

    def save_memory(self, role: str, content: str) -> None:
        """Append a message to history and persist."""
        self.history.append({"role": role, "content": content})
        # Trim if needed
        if len(self.history) > self.max_messages:
            self.history = self.history[-self.max_messages:]
        self._save()

    def get_context(self, max_chars: int = 4000) -> str:
        """Return recent conversation history as a formatted string."""
        lines = []
        for msg in self.history:
            role    = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        full = "\n".join(lines)
        return full[-max_chars:] if len(full) > max_chars else full

    def search_memory(self, query: str) -> List[Dict[str, str]]:
        """Return messages whose content contains the query (case-insensitive)."""
        q = query.lower()
        return [m for m in self.history if q in m.get("content", "").lower()]

    def get_stats(self) -> Dict[str, int]:
        """Return basic statistics about stored messages."""
        user_msgs      = sum(1 for m in self.history if m.get("role") == "user")
        assistant_msgs = sum(1 for m in self.history if m.get("role") == "assistant")
        return {
            "total_messages":     len(self.history),
            "user_messages":      user_msgs,
            "assistant_messages": assistant_msgs,
        }

    def clear(self) -> None:
        """Remove all messages from memory."""
        self.history = []
        self._save()
