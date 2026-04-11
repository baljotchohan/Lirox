"""
Lirox v3.0 — Session Store
Auto-names sessions, persists history, supports /history command.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from lirox.config import SESSIONS_DIR

# Maximum characters per message when building conversation context strings
CONTEXT_CONTENT_LIMIT: int = 400


def _generate_session_name(first_message: str) -> str:
    """Generate a short, readable session name from the first user message."""
    # Truncate + clean
    clean = re.sub(r'[^a-zA-Z0-9 ]', ' ', first_message).strip()
    words = clean.split()[:5]
    if not words:
        words = ["Session"]
    name = " ".join(w.capitalize() for w in words)
    ts = datetime.now().strftime("%b%d %H:%M")
    return f"{name} — {ts}"


class SessionEntry:
    def __init__(self, role: str, content: str, agent: str = "", mode: str = ""):
        self.role    = role       # "user" | "assistant"
        self.content = content
        self.agent   = agent
        self.mode    = mode
        self.ts      = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "role":    self.role,
            "content": self.content,
            "agent":   self.agent,
            "mode":    self.mode,
            "ts":      self.ts,
        }

    @staticmethod
    def from_dict(d: dict) -> "SessionEntry":
        e = SessionEntry(d["role"], d["content"], d.get("agent", ""), d.get("mode", ""))
        e.ts = d.get("ts", "")
        return e


class Session:
    def __init__(self, session_id: str = None, name: str = ""):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.name       = name
        self.created_at = datetime.now().isoformat()
        self.entries: List[SessionEntry] = []
        self.active_agent = "chat"
        self.thinking_mode = "complex"
        self.agent_explicitly_set: bool = False  # BUG-01/06 FIX: track explicit /agent switches

    def add(self, role: str, content: str, agent: str = "", mode: str = ""):
        # Auto-name on first user message
        if not self.name and role == "user":
            self.name = _generate_session_name(content)
        entry = SessionEntry(role, content, agent, mode)
        self.entries.append(entry)

    def to_dict(self) -> dict:
        return {
            "session_id":         self.session_id,
            "name":               self.name,
            "created_at":          self.created_at,
            "active_agent":       self.active_agent,
            "thinking_mode":      self.thinking_mode,
            "agent_explicitly_set": self.agent_explicitly_set,
            "entries":            [e.to_dict() for e in self.entries],
        }

    @staticmethod
    def from_dict(d: dict) -> "Session":
        s = Session(d["session_id"], d["name"])
        s.created_at     = d.get("created_at", "")
        s.active_agent   = d.get("active_agent", "chat")
        s.thinking_mode  = d.get("thinking_mode", "complex")
        s.agent_explicitly_set = d.get("agent_explicitly_set", False)
        s.entries        = [SessionEntry.from_dict(e) for e in d.get("entries", [])]
        return s

    def summary(self) -> str:
        """One-line summary for /history display."""
        count = sum(1 for e in self.entries if e.role == "user")
        name  = self.name or f"Session {self.session_id}"
        ts    = self.created_at[:16].replace("T", " ")
        return f"{name}  [{count} msgs, {ts}]"


class SessionStore:
    """
    Manages multiple chat sessions.
    Each session is stored as a JSON file in SESSIONS_DIR.
    """

    def __init__(self):
        self._current: Optional[Session] = None
        self._index: Dict[str, str] = {}  # {session_id: file_path}
        self._load_index()

    # ── Index Management ──────────────────────────────────────────────────────

    def _index_path(self) -> str:
        return os.path.join(SESSIONS_DIR, "_index.json")

    def _load_index(self):
        p = self._index_path()
        if os.path.exists(p):
            try:
                with open(p) as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}

    def _save_index(self):
        try:
            with open(self._index_path(), "w") as f:
                json.dump(self._index, f, indent=2)
        except Exception:
            pass

    # ── Session Lifecycle ────────────────────────────────────────────────────

    def new_session(self, agent: str = "chat", mode: str = "think", explicit: bool = False) -> Session:
        """Create a new session and make it current."""
        s = Session()
        s.active_agent  = agent
        s.thinking_mode = mode
        s.agent_explicitly_set = explicit
        self._current   = s
        return s

    def current(self) -> Session:
        if self._current is None:
            self._current = self.new_session()
        return self._current

    def save_current(self):
        if self._current is None:
            return
        fname = f"session_{self._current.session_id}.json"
        fpath = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(fpath, "w") as f:
                json.dump(self._current.to_dict(), f, indent=2)
            self._index[self._current.session_id] = fpath
            self._save_index()
        except Exception as e:
            # BUG-8 FIX: log instead of silently swallowing
            try:
                from lirox.utils.structured_logger import get_logger
                get_logger("lirox.sessions").error(
                    f"Session save failed [{self._current.session_id}]: {e}")
            except Exception:
                pass  # if logger itself fails, don't crash the agent

    def load_session(self, session_id: str) -> Optional[Session]:
        fpath = self._index.get(session_id)
        if fpath and os.path.exists(fpath):
            try:
                with open(fpath) as f:
                    return Session.from_dict(json.load(f))
            except Exception:
                pass
        return None

    def set_current(self, session: Session) -> None:
        """Make *session* the active session."""
        self._current = session

    # ── History ──────────────────────────────────────────────────────────────

    def list_sessions(self, limit: int = 20) -> List[Session]:
        sessions = []
        for sid, fpath in self._index.items():
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        s = Session.from_dict(json.load(f))
                        sessions.append(s)
                except Exception:
                    pass
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[:limit]

    def format_history(self, limit: int = 20) -> str:
        sessions = self.list_sessions(limit)
        if not sessions:
            return "No session history yet."
        lines = ["Recent Sessions:\n"]
        for i, s in enumerate(sessions, 1):
            lines.append(f"  {i:2}. [{s.session_id}]  {s.summary()}")
        return "\n".join(lines)

    # ── Context Export for Agents ────────────────────────────────────────────

    def get_context_for_agent(self, agent_name: str, limit: int = 10) -> str:
        """
        Get the full conversation history from the current session.

        Returns all recent messages (user + assistant) so agents have
        complete context of the ongoing conversation.  The *agent_name*
        parameter is kept for API compatibility but the method now returns
        the full exchange rather than filtering by agent.
        """
        session = self.current()
        # Return full conversation history (not filtered by agent)
        # so that each agent receives prior context regardless of which
        # sub-agent generated each reply (BUG-01 fix).
        recent = session.entries[-(limit * 2):]
        if not recent:
            return ""
        lines = []
        for e in recent:
            label = "User" if e.role == "user" else f"Assistant"
            lines.append(f"{label}: {e.content[:CONTEXT_CONTENT_LIMIT]}")
        return "\n".join(lines)
