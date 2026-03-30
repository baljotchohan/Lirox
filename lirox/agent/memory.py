"""
Lirox v0.3 — Enhanced Memory System

Conversation memory with:
- Persistent JSON storage
- Keyword search across history
- Relevance-scored context retrieval
- Memory statistics
"""

import json
import os
from datetime import datetime
from lirox.config import MEMORY_LIMIT


class Memory:
    """Conversation memory with search and relevance scoring."""

    def __init__(self, storage_file="memory.json"):
        self.storage_file = storage_file
        self.history = self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_memory(self, role, content):
        """Save a message to conversation history."""
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only the last N messages (limit * 2 for user/ai pairs)
        if len(self.history) > MEMORY_LIMIT * 2:
            self.history = self.history[-(MEMORY_LIMIT * 2):]

        with open(self.storage_file, 'w') as f:
            json.dump(self.history, f, indent=4)

    def get_context(self):
        """Returns formatted conversation history for injection into prompts."""
        if not self.history:
            return ""

        lines = ["--- Recent conversation ---"]
        for msg in self.history:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_name}: {msg['content']}")
        lines.append("--- End of history ---\n")
        return "\n".join(lines)

    def get_messages_for_api(self):
        """Returns history in OpenAI message format for providers that support it."""
        return [{"role": m["role"], "content": m["content"]} for m in self.history]

    # ─── v0.3 Additions ───────────────────────────────────────────────────────

    def search_memory(self, query, limit=5):
        """
        Search memory for exchanges containing the query keywords.

        Args:
            query: Search string
            limit: Max results to return

        Returns:
            List of matching message dicts, scored by relevance
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []

        for msg in self.history:
            content_lower = msg["content"].lower()

            # Score: exact phrase match = 10, word overlap = 1 per word
            score = 0
            if query_lower in content_lower:
                score += 10  # Exact substring match

            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            score += overlap

            if score > 0:
                scored.append((score, msg))

        # Sort by score (highest first), return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [msg for _, msg in scored[:limit]]

    def get_relevant_context(self, query, max_exchanges=10):
        """
        Get context most relevant to the current query.
        Uses keyword scoring to prioritize relevant exchanges.

        Args:
            query: Current user input
            max_exchanges: Max exchanges to include

        Returns:
            Formatted context string with relevant history
        """
        if not self.history:
            return ""

        relevant = self.search_memory(query, limit=max_exchanges)

        if not relevant:
            # Fallback to most recent if no relevant matches
            recent = self.history[-(max_exchanges * 2):]
            relevant = recent

        lines = ["--- Relevant context ---"]
        for msg in relevant:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_name}: {msg['content']}")
        lines.append("--- End of context ---\n")
        return "\n".join(lines)

    def get_stats(self):
        """
        Return memory statistics.

        Returns:
            Dict with stats about stored memory
        """
        if not self.history:
            return {
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "oldest": "N/A",
                "newest": "N/A"
            }

        user_msgs = sum(1 for m in self.history if m["role"] == "user")
        asst_msgs = sum(1 for m in self.history if m["role"] == "assistant")

        oldest = self.history[0].get("timestamp", "Unknown")
        newest = self.history[-1].get("timestamp", "Unknown")

        return {
            "total_messages": len(self.history),
            "user_messages": user_msgs,
            "assistant_messages": asst_msgs,
            "oldest": oldest,
            "newest": newest
        }

    def clear(self):
        """Clear all conversation memory."""
        self.history = []
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
        return "Conversation memory cleared."
