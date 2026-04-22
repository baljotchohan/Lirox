"""Lirox v1.0 — SQLite Database Store

Production-grade persistence layer using SQLite with:
  - WAL mode for concurrent access without blocking
  - Indexed queries for fast fact / conversation lookups
  - Schema migrations tracked in a version table
  - Atomic writes (transactions) with rollback on failure
  - Full-text search on conversations and facts (FTS5)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from lirox.database.models import (
    AuditEvent,
    Conversation,
    Fact,
    Project,
    UsageStat,
    UserProfile,
)

_logger = logging.getLogger("lirox.database")

# Current schema version — bump when adding migrations
_SCHEMA_VERSION = 2


class DatabaseStore:
    """Thread-safe SQLite store for all Lirox persistent data.

    Usage::

        db = DatabaseStore()               # opens default path
        db = DatabaseStore("/path/to.db")  # explicit path

    All public methods are safe to call from multiple threads simultaneously.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from lirox.config import DATA_DIR
            db_path = str(Path(DATA_DIR) / "lirox.db")
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    # ── Connection management ─────────────────────────────────────────────────

    @property
    def _conn(self) -> sqlite3.Connection:
        """Return a per-thread SQLite connection, creating it on first access."""
        if not getattr(self._local, "conn", None):
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that commits on success and rolls back on error."""
        conn = self._conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        """Close the per-thread connection if open."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

    # ── Schema management ─────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables and run any pending migrations."""
        with self._transaction() as conn:
            conn.executescript(_SCHEMA_DDL)
            self._run_migrations(conn)

    def _current_version(self, conn: sqlite3.Connection) -> int:
        try:
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return int(row["version"]) if row else 0
        except Exception:
            return 0

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        version = self._current_version(conn)
        for v, sql in _MIGRATIONS:
            if v > version:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (v, datetime.now(timezone.utc).isoformat()),
                )
                _logger.debug("Applied DB migration v%d", v)

    # ── User Profile ──────────────────────────────────────────────────────────

    def save_profile(self, profile: UserProfile) -> None:
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO user_profiles
                       (user_id, name, agent_name, profession, niche,
                        current_project, goals, preferences, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       name=excluded.name,
                       agent_name=excluded.agent_name,
                       profession=excluded.profession,
                       niche=excluded.niche,
                       current_project=excluded.current_project,
                       goals=excluded.goals,
                       preferences=excluded.preferences,
                       updated_at=excluded.updated_at""",
                (
                    profile.user_id,
                    profile.name,
                    profile.agent_name,
                    profile.profession,
                    profile.niche,
                    profile.current_project,
                    json.dumps(profile.goals),
                    json.dumps(profile.preferences),
                    profile.created_at,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def load_profile(self, user_id: str = "default") -> Optional[UserProfile]:
        row = self._conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None
        return UserProfile(
            user_id=row["user_id"],
            name=row["name"] or "",
            agent_name=row["agent_name"] or "Lirox",
            profession=row["profession"] or "",
            niche=row["niche"] or "",
            current_project=row["current_project"] or "",
            goals=_load_json(row["goals"], []),
            preferences=_load_json(row["preferences"], {}),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    # ── Conversations ─────────────────────────────────────────────────────────

    def add_conversation(self, msg: Conversation) -> int:
        with self._transaction() as conn:
            cur = conn.execute(
                """INSERT INTO conversations
                       (session_id, role, content, agent, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (msg.session_id, msg.role, msg.content, msg.agent, msg.timestamp),
            )
            return cur.lastrowid

    def get_conversations(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Conversation]:
        if session_id:
            rows = self._conn.execute(
                """SELECT * FROM conversations WHERE session_id = ?
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (session_id, limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM conversations
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [_row_to_conversation(r) for r in reversed(rows)]

    def search_conversations(self, query: str, limit: int = 20) -> List[Conversation]:
        """Full-text search across all conversation content."""
        try:
            rows = self._conn.execute(
                """SELECT c.* FROM conversations c
                   JOIN conversations_fts f ON c.id = f.rowid
                   WHERE conversations_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [_row_to_conversation(r) for r in rows]
        except sqlite3.OperationalError:
            # FTS5 not available — fall back to LIKE
            rows = self._conn.execute(
                "SELECT * FROM conversations WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            return [_row_to_conversation(r) for r in rows]

    def count_conversations(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM conversations").fetchone()
        return row[0] if row else 0

    # ── Facts ─────────────────────────────────────────────────────────────────

    def upsert_fact(self, fact: Fact) -> int:
        """Insert a new fact or increment times_seen if an identical one exists."""
        existing = self._conn.execute(
            "SELECT id, times_seen FROM facts WHERE content = ?", (fact.content,)
        ).fetchone()
        with self._transaction() as conn:
            if existing:
                conn.execute(
                    "UPDATE facts SET times_seen = ?, last_seen = ? WHERE id = ?",
                    (existing["times_seen"] + 1, datetime.now(timezone.utc).isoformat(), existing["id"]),
                )
                return existing["id"]
            cur = conn.execute(
                """INSERT INTO facts
                       (content, confidence, source, category, created_at, last_seen, times_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    fact.content,
                    fact.confidence,
                    fact.source,
                    fact.category,
                    fact.created_at,
                    fact.last_seen,
                    fact.times_seen,
                ),
            )
            return cur.lastrowid

    def get_facts(
        self, category: Optional[str] = None, limit: int = 100
    ) -> List[Fact]:
        if category:
            rows = self._conn.execute(
                """SELECT * FROM facts WHERE category = ?
                   ORDER BY confidence DESC, times_seen DESC LIMIT ?""",
                (category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM facts ORDER BY confidence DESC, times_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_fact(r) for r in rows]

    def search_facts(self, query: str, limit: int = 20) -> List[Fact]:
        """Full-text search across stored facts."""
        try:
            rows = self._conn.execute(
                """SELECT f.* FROM facts f
                   JOIN facts_fts ft ON f.id = ft.rowid
                   WHERE facts_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [_row_to_fact(r) for r in rows]
        except sqlite3.OperationalError:
            rows = self._conn.execute(
                "SELECT * FROM facts WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            return [_row_to_fact(r) for r in rows]

    def count_facts(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM facts").fetchone()
        return row[0] if row else 0

    # ── Projects ──────────────────────────────────────────────────────────────

    def upsert_project(self, project: Project) -> int:
        existing = self._conn.execute(
            "SELECT id FROM projects WHERE name = ?", (project.name,)
        ).fetchone()
        with self._transaction() as conn:
            if existing:
                conn.execute(
                    """UPDATE projects SET description=?, language=?, path=?,
                           status=?, updated_at=?, metadata=? WHERE id=?""",
                    (
                        project.description,
                        project.language,
                        project.path,
                        project.status,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(project.metadata),
                        existing["id"],
                    ),
                )
                return existing["id"]
            cur = conn.execute(
                """INSERT INTO projects
                       (name, description, language, path, status, created_at, updated_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project.name,
                    project.description,
                    project.language,
                    project.path,
                    project.status,
                    project.created_at,
                    project.updated_at,
                    json.dumps(project.metadata),
                ),
            )
            return cur.lastrowid

    def get_projects(self, status: Optional[str] = None) -> List[Project]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [_row_to_project(r) for r in rows]

    # ── Usage Statistics ──────────────────────────────────────────────────────

    def record_usage(self, stat: UsageStat) -> None:
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO usage_stats
                       (provider, model, prompt_tokens, completion_tokens,
                        total_tokens, cost_usd, latency_ms, success, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stat.provider,
                    stat.model,
                    stat.prompt_tokens,
                    stat.completion_tokens,
                    stat.total_tokens,
                    stat.cost_usd,
                    stat.latency_ms,
                    int(stat.success),
                    stat.timestamp,
                ),
            )

    def get_usage_summary(self) -> Dict[str, Any]:
        rows = self._conn.execute(
            """SELECT provider, SUM(total_tokens) as tokens,
                      SUM(cost_usd) as cost, COUNT(*) as calls
               FROM usage_stats GROUP BY provider"""
        ).fetchall()
        return {
            r["provider"]: {
                "total_tokens": r["tokens"],
                "cost_usd": round(r["cost"], 6),
                "calls": r["calls"],
            }
            for r in rows
        }

    # ── Audit Trail ───────────────────────────────────────────────────────────

    def audit(self, event: AuditEvent) -> None:
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO audit_trail
                       (action, target, status, detail, user_approved, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    event.action,
                    event.target,
                    event.status,
                    event.detail,
                    int(event.user_approved),
                    event.timestamp,
                ),
            )

    def get_audit_trail(self, limit: int = 100) -> List[AuditEvent]:
        rows = self._conn.execute(
            "SELECT * FROM audit_trail ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            AuditEvent(
                id=r["id"],
                action=r["action"],
                target=r["target"],
                status=r["status"],
                detail=r["detail"],
                user_approved=bool(r["user_approved"]),
                timestamp=r["timestamp"],
            )
            for r in rows
        ]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        return {
            "conversations": self.count_conversations(),
            "facts": self.count_facts(),
            "projects": len(self.get_projects()),
            "db_path": self._path,
            "db_size_bytes": os.path.getsize(self._path) if os.path.exists(self._path) else 0,
        }

    def backup(self, dest_path: str) -> bool:
        """Create a consistent backup of the database."""
        try:
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(dest_path) as backup_conn:
                self._conn.backup(backup_conn)
            return True
        except Exception as exc:
            _logger.error("Database backup failed: %s", exc)
            return False


# ── DDL ───────────────────────────────────────────────────────────────────────

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version    INTEGER NOT NULL,
    applied_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL DEFAULT '',
    agent_name      TEXT NOT NULL DEFAULT 'Lirox',
    profession      TEXT NOT NULL DEFAULT '',
    niche           TEXT NOT NULL DEFAULT '',
    current_project TEXT NOT NULL DEFAULT '',
    goals           TEXT NOT NULL DEFAULT '[]',
    preferences     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL DEFAULT '',
    role       TEXT    NOT NULL DEFAULT 'user',
    content    TEXT    NOT NULL DEFAULT '',
    agent      TEXT    NOT NULL DEFAULT 'personal',
    timestamp  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_session  ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_time     ON conversations(timestamp);

CREATE TABLE IF NOT EXISTS facts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT    NOT NULL UNIQUE,
    confidence REAL    NOT NULL DEFAULT 1.0,
    source     TEXT    NOT NULL DEFAULT 'interaction',
    category   TEXT    NOT NULL DEFAULT 'general',
    created_at TEXT    NOT NULL,
    last_seen  TEXT    NOT NULL,
    times_seen INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_conf     ON facts(confidence DESC);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    language    TEXT    NOT NULL DEFAULT '',
    path        TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'active',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    metadata    TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_proj_status ON projects(status);

CREATE TABLE IF NOT EXISTS usage_stats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    provider         TEXT    NOT NULL DEFAULT '',
    model            TEXT    NOT NULL DEFAULT '',
    prompt_tokens    INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd         REAL    NOT NULL DEFAULT 0.0,
    latency_ms       REAL    NOT NULL DEFAULT 0.0,
    success          INTEGER NOT NULL DEFAULT 1,
    timestamp        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage_stats(provider);
CREATE INDEX IF NOT EXISTS idx_usage_time     ON usage_stats(timestamp);

CREATE TABLE IF NOT EXISTS audit_trail (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    action        TEXT    NOT NULL DEFAULT '',
    target        TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'ok',
    detail        TEXT    NOT NULL DEFAULT '',
    user_approved INTEGER NOT NULL DEFAULT 0,
    timestamp     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_trail(action);
CREATE INDEX IF NOT EXISTS idx_audit_time   ON audit_trail(timestamp);
"""

# ── Migrations (version -> SQL) ───────────────────────────────────────────────

_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        # Add FTS5 virtual tables for full-text search
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
            USING fts5(content, content='conversations', content_rowid='id');

        CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
            USING fts5(content, content='facts', content_rowid='id');

        CREATE TRIGGER IF NOT EXISTS conv_ai AFTER INSERT ON conversations BEGIN
            INSERT INTO conversations_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS conv_ad AFTER DELETE ON conversations BEGIN
            INSERT INTO conversations_fts(conversations_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS fact_ai AFTER INSERT ON facts BEGIN
            INSERT INTO facts_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS fact_ad AFTER DELETE ON facts BEGIN
            INSERT INTO facts_fts(facts_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
        END;
        """,
    ),
    (
        2,
        # Ensure schema_version has the initial row if upgrading from plain DDL
        "",
    ),
]


# ── Row → model helpers ───────────────────────────────────────────────────────

def _load_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _row_to_conversation(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        agent=row["agent"],
        timestamp=row["timestamp"],
    )


def _row_to_fact(row: sqlite3.Row) -> Fact:
    return Fact(
        id=row["id"],
        content=row["content"],
        confidence=row["confidence"],
        source=row["source"],
        category=row["category"],
        created_at=row["created_at"],
        last_seen=row["last_seen"],
        times_seen=row["times_seen"],
    )


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        language=row["language"],
        path=row["path"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=_load_json(row["metadata"], {}),
    )
