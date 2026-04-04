"""Lirox v2.0 — Agent Memory

Lightweight conversation-history store with keyword search and persistence.
Used by older agent tests (lirox.agent.memory); the production v2 memory lives
in lirox.memory.manager.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class Memory:
    """
    Simple JSON-backed conversation memory.

    Each entry is stored as::

        {"role": "user"|"assistant", "content": "..."}

    Parameters
    ----------
    storage_file:
        Path (relative or absolute) to the JSON persistence file.
        Pass ``None`` to disable persistence (in-memory only).
    """

    def __init__(self, storage_file: Optional[str] = None):
        self.storage_file = storage_file
        self.history: List[Dict[str, str]] = []
        if storage_file and os.path.exists(storage_file):
            self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def save_memory(self, role: str, content: str) -> None:
        """Append a message to history and persist."""
        self.history.append({"role": role, "content": content})
        self._save()

    def get_context(self, max_entries: int = 50) -> str:
        """Return a plain-text view of recent history."""
        recent = self.history[-max_entries:]
        lines = [f"{e['role'].capitalize()}: {e['content']}" for e in recent]
        return "\n".join(lines)

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict[str, str]]:
        """Return entries whose content contains any word from *query* (case-insensitive)."""
        keywords = query.lower().split()
        matches = []
        for entry in self.history:
            content_lower = entry["content"].lower()
            if any(kw in content_lower for kw in keywords):
                matches.append(entry)
        return matches[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Return message count statistics."""
        user_count = sum(1 for e in self.history if e["role"] == "user")
        assistant_count = sum(1 for e in self.history if e["role"] == "assistant")
        return {
            "total_messages": len(self.history),
            "user_messages": user_count,
            "assistant_messages": assistant_count,
        }

    def clear(self) -> None:
        """Remove all history and delete the persistence file if it exists."""
        self.history = []
        if self.storage_file and os.path.exists(self.storage_file):
            os.remove(self.storage_file)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        if not self.storage_file:
            return
        Path(self.storage_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_file, "w", encoding="utf-8") as fh:
            json.dump(self.history, fh, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        try:
            with open(self.storage_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                self.history = data
        except (json.JSONDecodeError, OSError):
            self.history = []
