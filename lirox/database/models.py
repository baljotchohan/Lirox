"""Lirox v1.0 — Database Models

Lightweight dataclasses representing the core database entities.
No ORM dependency — plain Python objects serialised to/from SQLite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserProfile:
    """Stored user profile and preferences."""
    user_id: str = "default"
    name: str = ""
    agent_name: str = "Lirox"
    profession: str = ""
    niche: str = ""
    current_project: str = ""
    goals: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass
class Conversation:
    """A single message in conversation history."""
    id: Optional[int] = None
    session_id: str = ""
    role: str = "user"          # "user" | "assistant" | "system"
    content: str = ""
    agent: str = "personal"
    timestamp: str = field(default_factory=_now)


@dataclass
class Fact:
    """A learned fact about the user."""
    id: Optional[int] = None
    content: str = ""
    confidence: float = 1.0
    source: str = "interaction"  # "interaction" | "manual" | "import"
    category: str = "general"
    created_at: str = field(default_factory=_now)
    last_seen: str = field(default_factory=_now)
    times_seen: int = 1


@dataclass
class Project:
    """A user project tracked by Lirox."""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    language: str = ""
    path: str = ""
    status: str = "active"      # "active" | "paused" | "done"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageStat:
    """Per-provider token / call statistics."""
    id: Optional[int] = None
    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    timestamp: str = field(default_factory=_now)


@dataclass
class AuditEvent:
    """Immutable record of every autonomous action taken."""
    id: Optional[int] = None
    action: str = ""             # e.g. "file_write", "shell_exec", "llm_call"
    target: str = ""             # file path, command, etc.
    status: str = "ok"           # "ok" | "blocked" | "error"
    detail: str = ""
    user_approved: bool = False
    timestamp: str = field(default_factory=_now)
