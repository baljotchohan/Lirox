"""Lirox v1.0 — Learning Manager

High-level API that:
  - Orchestrates fact extraction from conversations
  - Persists learned data to both the JSON LearningsStore (mind/) and SQLite (database/)
  - Deduplicates facts before saving
  - Provides a unified interface for querying what Lirox knows
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("lirox.learning.manager")


class LearningManager:
    """Unified interface for Lirox's self-learning system.

    Combines the JSON-backed LearningsStore (for backwards compatibility)
    with the SQLite DatabaseStore (for advanced queries).

    Example::

        mgr = LearningManager()
        stats = mgr.train_from_memory(memory_manager, session_store)
        print(stats)
        print(mgr.recall_facts(limit=5))
    """

    def __init__(self, provider: str = "auto", use_db: bool = True):
        self._provider = provider
        self._use_db = use_db
        self._learnings: Optional[Any] = None
        self._db: Optional[Any] = None

    @property
    def learnings(self):
        if self._learnings is None:
            from lirox.mind.learnings import LearningsStore
            self._learnings = LearningsStore()
        return self._learnings

    @property
    def db(self):
        if self._db is None and self._use_db:
            try:
                from lirox.database.store import DatabaseStore
                self._db = DatabaseStore()
            except Exception as exc:
                _logger.warning("SQLite database unavailable: %s", exc)
                self._db = None
        return self._db

    # ── Training ─────────────────────────────────────────────────────────────

    def train_from_memory(self, memory_manager=None, session_store=None) -> Dict[str, int]:
        """Extract learnings from memory and session history.

        Delegates to :class:`lirox.mind.trainer.TrainingEngine` and
        additionally persists new facts to SQLite if available.

        Returns a stats dict with keys: facts_added, topics_bumped,
        preferences_added, projects_found.
        """
        from lirox.mind.trainer import TrainingEngine
        engine = TrainingEngine(self.learnings)
        stats = engine.train(memory_manager, session_store)

        if self.db and stats.get("facts_added", 0) > 0:
            self._sync_facts_to_db()

        return stats

    def train_from_text(self, conversation: str) -> Dict[str, int]:
        """Extract and save learnings from raw *conversation* text.

        Returns same stats dict as :meth:`train_from_memory`.
        """
        from lirox.learning.extractor import FactExtractor
        extractor = FactExtractor(provider=self._provider)
        knowledge = extractor.extract(conversation)

        if knowledge.error:
            _logger.warning("Extraction failed: %s", knowledge.error)
            return {"facts_added": 0, "topics_bumped": 0, "preferences_added": 0, "projects_found": 0}

        stats = {"facts_added": 0, "topics_bumped": 0, "preferences_added": 0, "projects_found": 0}

        for fact in knowledge.facts:
            try:
                self.learnings.add_fact(fact)
                stats["facts_added"] += 1
            except Exception:
                pass

        for topic in knowledge.topics:
            try:
                self.learnings.bump_topic(topic)
                stats["topics_bumped"] += 1
            except Exception:
                pass

        for category, prefs in knowledge.preferences.items():
            for pref in prefs:
                try:
                    self.learnings.add_preference(category, pref)
                    stats["preferences_added"] += 1
                except Exception:
                    pass

        for project in knowledge.projects:
            try:
                self.learnings.add_or_update_project(
                    project.get("name", ""),
                    project.get("description", ""),
                )
                stats["projects_found"] += 1
            except Exception:
                pass

        try:
            self.learnings.flush()
        except Exception:
            pass

        if self.db:
            self._sync_facts_to_db()

        return stats

    # ── Recall ───────────────────────────────────────────────────────────────

    def recall_facts(self, limit: int = 20) -> List[str]:
        """Return the top *limit* learned facts."""
        try:
            facts = self.learnings.data.get("user_facts", [])
            return [f.get("fact", "") for f in facts[-limit:] if f.get("fact")]
        except Exception:
            return []

    def recall_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the top *limit* interest topics."""
        try:
            return self.learnings.get_top_topics(limit)
        except Exception:
            return []

    def recall_projects(self) -> List[Dict[str, Any]]:
        """Return tracked projects."""
        try:
            return self.learnings.data.get("projects", [])
        except Exception:
            return []

    def search_knowledge(self, query: str, limit: int = 10) -> List[str]:
        """Search learned facts for *query* (substring match)."""
        q = query.lower()
        matches = []
        try:
            for entry in self.learnings.data.get("user_facts", []):
                fact = entry.get("fact", "")
                if q in fact.lower():
                    matches.append(fact)
                    if len(matches) >= limit:
                        break
        except Exception:
            pass

        # Also search SQLite if available
        if self.db and len(matches) < limit:
            try:
                db_facts = self.db.search_facts(query, limit=limit - len(matches))
                for f in db_facts:
                    if f.content not in matches:
                        matches.append(f.content)
            except Exception:
                pass

        return matches

    def stats(self) -> Dict[str, Any]:
        """Return learning statistics."""
        base = {
            "facts": len(self.learnings.data.get("user_facts", [])),
            "topics": len(self.learnings.data.get("topics", {})),
            "projects": len(self.learnings.data.get("projects", [])),
            "preferences": sum(
                len(v) for v in self.learnings.data.get("preferences", {}).values()
            ),
        }
        if self.db:
            try:
                base["db_facts"] = self.db.count_facts()
            except Exception:
                pass
        return base

    # ── Internal sync ─────────────────────────────────────────────────────────

    def _sync_facts_to_db(self) -> None:
        """Mirror JSON-stored facts into SQLite for searchability."""
        if not self.db:
            return
        from lirox.database.models import Fact
        from datetime import datetime
        try:
            for entry in self.learnings.data.get("user_facts", []):
                fact_text = entry.get("fact", "")
                if not fact_text:
                    continue
                self.db.upsert_fact(Fact(
                    content=fact_text,
                    confidence=entry.get("confidence", 1.0),
                    source=entry.get("source", "interaction"),
                    category="user_fact",
                    created_at=entry.get("added_at", datetime.now(timezone.utc).isoformat()),
                    last_seen=datetime.now(timezone.utc).isoformat(),
                ))
        except Exception as exc:
            _logger.debug("Fact sync to DB failed: %s", exc)
