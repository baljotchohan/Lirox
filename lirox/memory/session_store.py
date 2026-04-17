"""Lirox v2.0.0 — Session Store

Manages chat sessions with persistent storage.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from lirox.config import SESSIONS_DIR

CONTEXT_CONTENT_LIMIT: int = 400


def _generate_session_name(first_message: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9 ]", " ", first_message).strip()
    words = clean.split()[:5]
    if not words:
        words = ["Session"]
    name = " ".join(w.capitalize() for w in words)
    ts = datetime.now().strftime("%b%d %H:%M")
    return f"{name} — {ts}"


class SessionEntry:
    def __init__(self, role: str, content: str, agent: str = "", mode: str = ""):
        self.role    = role
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

    def add(self, role: str, content: str, agent: str = "", mode: str = "") -> None:
        if not self.name and role == "user":
            self.name = _generate_session_name(content)
        self.entries.append(SessionEntry(role, content, agent, mode))

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name":       self.name,
            "created_at": self.created_at,
            "entries":    [e.to_dict() for e in self.entries],
        }

    @staticmethod
    def from_dict(d: dict) -> "Session":
        s = Session(d["session_id"], d["name"])
        s.created_at = d.get("created_at", "")
        s.entries = [SessionEntry.from_dict(e) for e in d.get("entries", [])]
        return s

    def summary(self) -> str:
        count = sum(1 for e in self.entries if e.role == "user")
        name = self.name or f"Session {self.session_id}"
        ts    = self.created_at[:16].replace("T", " ")
        return f"{name}  [{count} msgs, {ts}]"


class SessionStore:
    """Manages multiple chat sessions; each saved as a JSON file."""

    def __init__(self):
        self._current: Optional[Session] = None
        self._index: Dict[str, str] = {}
        self._load_index()

    def _index_path(self) -> str:
        return os.path.join(SESSIONS_DIR, "_index.json")

    def _load_index(self) -> None:
        p = self._index_path()
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}

    def _save_index(self) -> None:
        try:
            with open(self._index_path(), "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2)
        except Exception:
            pass

    def new_session(self) -> Session:
        s = Session()
        self._current = s
        return s

    def current(self) -> Session:
        if self._current is None:
            self._current = self.new_session()
        return self._current

    def save_current(self) -> None:
        if self._current is None:
            return
        fname = f"session_{self._current.session_id}.json"
        fpath = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(self._current.to_dict(), f, indent=2)
            self._index[self._current.session_id] = fpath
            self._save_index()
        except Exception:
            pass

    def list_sessions(self, limit: int = 20) -> List[Session]:
        sessions = []
        for sid, fpath in self._index.items():
            if os.path.exists(fpath):
                try:
                    with open(fpath, encoding="utf-8") as f:
                        sessions.append(Session.from_dict(json.load(f)))
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

    def get_context(self, limit: int = 10) -> str:
        """Get recent conversation context from current session."""
        session = self.current()
        recent  = session.entries[-(limit * 2):]
        if not recent:
            return ""
        lines = []
        for e in recent:
            label = "User" if e.role == "user" else "Assistant"
            lines.append(f"{label}: {e.content[:CONTEXT_CONTENT_LIMIT]}")
        return "\n".join(lines)
