"""
Lirox v1.0.0 — Session Manager

High-level manager for chat sessions that wraps ``SessionStore`` with
convenience methods for creating, switching, and summarising sessions.
Provides a single shared instance (``get_session_manager()``) so that
all components work with the same session state.
"""

from __future__ import annotations

from typing import Optional

from lirox.memory.session_store import Session, SessionStore


class SessionManager:
    """
    Manage the lifecycle of chat sessions.

    This class wraps :class:`~lirox.memory.session_store.SessionStore`
    and adds a thin convenience layer: automatic session creation on
    first access, easy agent/mode switching, and a shared-instance
    accessor (:func:`get_session_manager`).
    """

    def __init__(self) -> None:
        self._store = SessionStore()

    # ── Session access ────────────────────────────────────────────────────────

    def current_session(self) -> Session:
        """
        Return the active session, creating a new one if none exists.

        Returns:
            The current :class:`~lirox.memory.session_store.Session`.
        """
        return self._store.current()

    def new_session(
        self,
        agent: str = "chat",
        mode: str = "think",
        explicit: bool = False,
    ) -> Session:
        """
        Create and activate a new session.

        Args:
            agent:    Initial active agent for the session.
            mode:     Thinking mode (``"think"`` or ``"fast"``).
            explicit: Whether the agent was explicitly selected by the
                      user (vs. auto-routed).

        Returns:
            The newly created :class:`~lirox.memory.session_store.Session`.
        """
        session = self._store.new_session(agent=agent, mode=mode, explicit=explicit)
        self._store.save_current()
        return session

    def load_session(self, session_id: str) -> Optional[Session]:
        """
        Load a previously saved session by ID and make it current.

        Args:
            session_id: Short session identifier (e.g. ``"a1b2c3d4"``).

        Returns:
            The loaded session, or ``None`` if not found.
        """
        session = self._store.load_session(session_id)
        if session is not None:
            self._store._current = session  # noqa: SLF001
        return session

    def save(self) -> None:
        """Persist the current session to disk."""
        self._store.save_current()

    # ── Agent / mode helpers ──────────────────────────────────────────────────

    def set_agent(self, agent_name: str, explicit: bool = True) -> None:
        """
        Switch the active agent on the current session.

        Args:
            agent_name: Name of the agent to activate.
            explicit:   Whether this switch was triggered by the user.
        """
        session = self.current_session()
        session.active_agent = agent_name
        if explicit:
            session.agent_explicitly_set = True
        self._store.save_current()

    def set_mode(self, mode: str) -> None:
        """
        Change the thinking mode for the current session.

        Args:
            mode: ``"think"`` or ``"fast"``.
        """
        self.current_session().thinking_mode = mode
        self._store.save_current()

    # ── History and context ───────────────────────────────────────────────────

    def history(self, limit: int = 20) -> str:
        """
        Return a formatted history of recent sessions.

        Args:
            limit: Maximum number of sessions to list.

        Returns:
            Multi-line string suitable for display.
        """
        return self._store.format_history(limit=limit)

    def get_context(self, agent_name: str, limit: int = 10) -> str:
        """
        Retrieve recent exchanges from the current session for *agent_name*.

        Args:
            agent_name: Agent whose exchanges should be included.
            limit:      Number of exchanges to return.

        Returns:
            Formatted context string.
        """
        return self._store.get_context_for_agent(agent_name, limit=limit)

    def add_exchange(
        self,
        user_message: str,
        assistant_message: str,
        agent: str = "",
        mode: str = "",
    ) -> None:
        """
        Record a user/assistant exchange in the current session.

        Args:
            user_message:      The user's input.
            assistant_message: The agent's response.
            agent:             Agent name that produced the response.
            mode:              Thinking mode used.
        """
        session = self.current_session()
        session.add("user",      user_message,      agent=agent, mode=mode)
        session.add("assistant", assistant_message, agent=agent, mode=mode)
        self._store.save_current()

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Return a lightweight snapshot of the manager's current state.

        Returns:
            A dict with keys:

            * ``session_id``    (str)
            * ``session_name``  (str)
            * ``active_agent``  (str)
            * ``thinking_mode`` (str)
            * ``message_count`` (int)
        """
        session = self.current_session()
        return {
            "session_id":    session.session_id,
            "session_name":  session.name,
            "active_agent":  session.active_agent,
            "thinking_mode": session.thinking_mode,
            "message_count": len(session.entries),
        }


# ── Module-level shared instance ─────────────────────────────────────────────

_INSTANCE: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Return the shared :class:`SessionManager` instance (singleton).

    The instance is created lazily on the first call.

    Returns:
        The shared :class:`SessionManager`.
    """
    global _INSTANCE  # noqa: PLW0603
    if _INSTANCE is None:
        _INSTANCE = SessionManager()
    return _INSTANCE
