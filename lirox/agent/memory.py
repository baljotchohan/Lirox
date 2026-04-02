"""
Lirox v0.5 — Enhanced Memory System

Conversation memory with:
- Persistent JSON storage anchored to PROJECT_ROOT (not CWD)
- Keyword search across history with relevance scoring
- Memory statistics
"""

import json
import os
from datetime import datetime
from lirox.config import MEMORY_LIMIT, PROJECT_ROOT


class Memory:
    """Conversation memory with search and relevance scoring."""

    def __init__(self, storage_file: str = None):
        # Anchor storage path to PROJECT_ROOT so it works from any CWD
        if storage_file is None:
            storage_file = os.path.join(PROJECT_ROOT, "memory.json")
        self.storage_file = storage_file
        self.history = self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_memory(self, role: str, content: str):
        """Save a message to conversation history."""
        self.history.append({
            "role":      role,
            "content":   content,
            "timestamp": datetime.now().isoformat()
        })
        # [FIX #6] Limit memory by MEMORY_LIMIT
        if len(self.history) > MEMORY_LIMIT:
            first_msg = self.history[0]
            # Retain roughly half of MEMORY_LIMIT elements
            keep = max(10, MEMORY_LIMIT // 2)
            self.history = [first_msg] + self.history[-keep:]

        with open(self.storage_file, "w") as f:
            json.dump(self.history, f, indent=4)

    def get_context(self) -> str:
        """Returns formatted conversation history for injection into prompts."""
        if not self.history:
            return ""

        lines = ["--- Recent conversation ---"]
        for msg in self.history:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_name}: {msg['content']}")
        lines.append("--- End of history ---\n")
        return "\n".join(lines)

    def get_messages_for_api(self) -> list:
        """Returns history in OpenAI message format for providers that support it."""
        return [{"role": m["role"], "content": m["content"]} for m in self.history]

    # ─── v0.3+ Search & Context ───────────────────────────────────────────────

    def search_memory(self, query: str, limit: int = 5) -> list:
        """
        Search memory for exchanges containing the query keywords.

        Returns: List of matching message dicts, scored by relevance.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []

        for msg in self.history:
            content_lower = msg["content"].lower()

            score = 0
            if query_lower in content_lower:
                score += 10  # Exact substring match bonus

            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            score += overlap

            if score > 0:
                scored.append((score, msg))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [msg for _, msg in scored[:limit]]

    def get_relevant_context(self, query: str, max_exchanges: int = 10) -> str:
        """
        Get context most relevant to the current query.
        Uses keyword scoring to prioritize relevant exchanges.
        """
        if not self.history:
            return ""

        relevant = self.search_memory(query, limit=max_exchanges)

        if not relevant:
            # Fallback to most recent
            recent = self.history[-(max_exchanges * 2):]
            relevant = recent

        lines = ["--- Relevant context ---"]
        for msg in relevant:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_name}: {msg['content']}")
        lines.append("--- End of context ---\n")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        return self.get_memory_stats()

    def get_memory_stats(self) -> dict:
        """[FIX #6] Return memory statistics."""
        if not self.history:
            return {
                "total_messages":     0,
                "user_messages":      0,
                "assistant_messages": 0,
                "oldest":             "N/A",
                "newest":             "N/A",
            }

        user_msgs = sum(1 for m in self.history if m["role"] == "user")
        asst_msgs = sum(1 for m in self.history if m["role"] == "assistant")

        return {
            "total_messages":     len(self.history),
            "user_messages":      user_msgs,
            "assistant_messages": asst_msgs,
            "oldest":             self.history[0].get("timestamp", "Unknown"),
            "newest":             self.history[-1].get("timestamp", "Unknown"),
        }

    def clear(self) -> str:
        """Clear all conversation memory."""
        self.history = []
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
        return "Conversation memory cleared."
