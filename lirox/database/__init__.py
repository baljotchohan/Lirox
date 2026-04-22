"""Lirox v1.0 — Database Package

SQLite-backed persistence layer for user profiles, conversation history,
learned facts, projects, usage statistics, and audit trails.
"""
from lirox.database.store import DatabaseStore
from lirox.database.models import (
    Conversation,
    Fact,
    Project,
    UsageStat,
    AuditEvent,
    UserProfile,
)

__all__ = [
    "DatabaseStore",
    "Conversation",
    "Fact",
    "Project",
    "UsageStat",
    "AuditEvent",
    "UserProfile",
]
