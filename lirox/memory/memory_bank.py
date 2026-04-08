"""
Lirox v1.0.0 — Memory Bank

Enhanced per-agent memory wrapper that builds on top of ``MemoryManager``
to provide a simple key-value store with query-based context retrieval,
full isolation by agent namespace, and snapshot capabilities.
"""

from __future__ import annotations

from typing import Any, Optional

from lirox.memory.manager import MemoryManager


class MemoryBank:
    """
    Enhanced, fully-isolated memory store for a single agent.

    ``MemoryBank`` wraps :class:`~lirox.memory.manager.MemoryManager` and
    adds a simple ``dict``-backed key-value layer on top of the long-term
    facts store.  Every instance is scoped to one *agent_name*, so two
    agents with different names can never read each other's data.

    Usage::

        bank = MemoryBank("code")
        bank.store("last_file", "main.py")
        path = bank.retrieve("last_file")  # "main.py"
        ctx  = bank.get_context("what file was last edited?")
    """

    def __init__(self, agent_name: str) -> None:
        """
        Initialise the bank for the given agent.

        Args:
            agent_name: Unique identifier for the agent that owns this
                        memory bank (used as namespace).
        """
        self._agent_name = agent_name
        self._manager    = MemoryManager(agent_name=agent_name)
        # In-process key-value store (not persisted across restarts)
        self._kv: dict[str, Any] = {}

    # ── Key-value interface ───────────────────────────────────────────────────

    def store(self, key: str, value: Any) -> None:
        """
        Store a value under *key*.

        The value is also recorded as a long-term fact so that it
        survives cross-session context queries.

        Args:
            key:   Identifier for the stored value.
            value: Arbitrary value (will be ``str()``-coerced for the
                   fact store).
        """
        self._kv[key] = value
        self._manager.add_fact(f"{key}: {value}")

    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve a value by *key*.

        Args:
            key: Identifier to look up.

        Returns:
            The stored value, or ``None`` if the key is unknown.
        """
        return self._kv.get(key)

    def clear(self) -> None:
        """
        Clear all in-process key-value pairs.

        This does **not** purge the persisted long-term facts managed by
        ``MemoryManager``; those survive across clear calls deliberately.
        """
        self._kv.clear()

    # ── Context retrieval ─────────────────────────────────────────────────────

    def get_context(self, query: str) -> str:
        """
        Return conversation context relevant to *query*.

        Delegates to
        :meth:`~lirox.memory.manager.MemoryManager.get_relevant_context`
        for semantic filtering.

        Args:
            query: Natural-language query to match against stored memory.

        Returns:
            A formatted context string, or an empty string if nothing
            relevant is found.
        """
        return self._manager.get_relevant_context(query)

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Return a point-in-time snapshot of the bank's state.

        Returns:
            A dict with keys:

            * ``agent_name``  (str)
            * ``kv_store``    (dict) – copy of the in-process KV pairs
            * ``stats``       (dict) – from
              :meth:`~lirox.memory.manager.MemoryManager.get_stats`
        """
        return {
            "agent_name": self._agent_name,
            "kv_store":   dict(self._kv),
            "stats":      self._manager.get_stats(),
        }
