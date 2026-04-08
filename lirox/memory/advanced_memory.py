"""
Lirox v2.0 — Advanced Memory System

Extended memory capabilities beyond the basic conversation buffer:
- Episodic memory (past events with timestamps)
- Semantic memory (concepts and facts)
- Procedural memory (learned procedures)
- Associative retrieval
- Memory compression and summarization
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    """A single item in advanced memory."""
    content:   str
    memory_type: str        # "episodic" | "semantic" | "procedural"
    importance: float = 0.5  # 0.0–1.0
    tags:      List[str]    = field(default_factory=list)
    ts:        float        = field(default_factory=time.time)
    access_count: int       = 0


class AdvancedMemory:
    """
    Multi-tier memory system with episodic, semantic, and procedural stores.

    Usage:
        mem = AdvancedMemory()
        mem.remember("User prefers dark mode", memory_type="semantic", importance=0.8)
        results = mem.recall("user preferences", top_k=5)
    """

    def __init__(self, max_entries: int = 10_000):
        self._entries:   List[MemoryEntry] = []
        self._max_entries = max_entries

    # ── Storage ───────────────────────────────────────────────────────────────

    def remember(
        self,
        content: str,
        memory_type: str = "episodic",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """
        Store a new memory entry.

        Args:
            content:     The information to remember.
            memory_type: "episodic", "semantic", or "procedural".
            importance:  Importance score 0.0–1.0 (higher = retained longer).
            tags:        Optional categorization tags.

        Returns:
            The created MemoryEntry.
        """
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
        )
        self._entries.append(entry)
        self._prune()
        return entry

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def recall(self, query: str, top_k: int = 10) -> List[MemoryEntry]:
        """
        Retrieve the most relevant memories for a query.

        Uses keyword matching with importance weighting.

        Args:
            query: Search string.
            top_k: Maximum number of results.

        Returns:
            List of matching MemoryEntry objects, sorted by relevance.
        """
        query_words = set(query.lower().split())
        scored: List[tuple] = []

        for entry in self._entries:
            entry_words = set(entry.content.lower().split())
            overlap = len(query_words & entry_words)
            if overlap > 0:
                score = overlap * entry.importance + 0.01 * entry.access_count
                scored.append((score, entry))

        # Sort by score desc, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [e for _, e in scored[:top_k]]

        # Increment access count
        for entry in results:
            entry.access_count += 1

        return results

    def recall_by_type(self, memory_type: str) -> List[MemoryEntry]:
        """Return all entries of a specific memory type."""
        return [e for e in self._entries if e.memory_type == memory_type]

    def recall_by_tag(self, tag: str) -> List[MemoryEntry]:
        """Return all entries with a specific tag."""
        return [e for e in self._entries if tag in e.tags]

    # ── Management ───────────────────────────────────────────────────────────

    def forget(self, entry: MemoryEntry) -> bool:
        """Remove a specific memory entry."""
        try:
            self._entries.remove(entry)
            return True
        except ValueError:
            return False

    def clear(self, memory_type: Optional[str] = None) -> int:
        """
        Clear memories.

        Args:
            memory_type: If specified, only clear that type.
                         If None, clear all memories.

        Returns:
            Number of entries removed.
        """
        if memory_type is None:
            count = len(self._entries)
            self._entries = []
            return count
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.memory_type != memory_type]
        return before - len(self._entries)

    def summarize(self) -> Dict[str, Any]:
        """Return statistics about current memory contents."""
        type_counts: Dict[str, int] = {}
        for entry in self._entries:
            type_counts[entry.memory_type] = type_counts.get(entry.memory_type, 0) + 1

        return {
            "total_entries":   len(self._entries),
            "by_type":         type_counts,
            "avg_importance":  (
                sum(e.importance for e in self._entries) / len(self._entries)
                if self._entries else 0.0
            ),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _prune(self) -> None:
        """Remove low-importance entries when at capacity."""
        if len(self._entries) <= self._max_entries:
            return
        # Sort by importance ascending, remove the least important
        self._entries.sort(key=lambda e: e.importance)
        excess = len(self._entries) - self._max_entries
        self._entries = self._entries[excess:]
