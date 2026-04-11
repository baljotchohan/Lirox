"""
Lirox v0.5 — Permanent Learnings Store

This is the Mind Agent's long-term knowledge base.
Every /train call crystallizes session patterns into permanent learnings.
"""
from __future__ import annotations

import atexit
import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from lirox.config import MIND_LEARN_FILE


class LearningsStore:
    """
    Persistent knowledge base for the Mind Agent.
    Stores facts, preferences, patterns, and skills learned from the user.
    """

    SCHEMA = {
        "version": "4.0",
        "created_at": None,
        "last_trained": None,
        "user_facts": [],          # Hard facts about the user
        "preferences": {},         # Category → list of preferences
        "topics": {},              # Topic → frequency + last_seen
        "communication_style": {}, # How user likes to communicate
        "projects": [],            # Active projects the user mentioned
        "dislikes": [],            # Things user explicitly doesn't like
        "interaction_patterns": {},# Time patterns, query types, etc.
        "custom_notes": [],        # User-added manual notes
        "sessions_trained": 0,
        "total_interactions": 0,
    }

    def __init__(self):
        self._path = Path(MIND_LEARN_FILE)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
        self._dirty = False   # BUG-4 FIX: track unsaved topic changes
        self._bump_count = 0  # BUG-H2 FIX: track bumps for periodic auto-save
        # BUG-H2 FIX: register atexit flush so dirty data is never lost on exit
        atexit.register(self.flush)

    def _load(self) -> Dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        d = dict(self.SCHEMA)
        d["created_at"] = datetime.now().isoformat()
        return d

    def save(self) -> None:
        self._path.write_text(json.dumps(self.data, indent=2, default=str))
        self._dirty = False

    # ── Add learnings ─────────────────────────────────────────────────────────

    def add_fact(self, fact: str, confidence: float = 1.0, source: str = "interaction") -> None:
        """Add a fact about the user."""
        # Avoid duplicates
        existing = [f["fact"].lower() for f in self.data["user_facts"]]
        if fact.lower() in existing:
            return
        self.data["user_facts"].append({
            "fact": fact,
            "confidence": confidence,
            "source": source,
            "learned_at": datetime.now().isoformat(),
        })
        # Keep latest 200 facts
        if len(self.data["user_facts"]) > 200:
            # Drop lowest confidence first
            self.data["user_facts"].sort(key=lambda x: x["confidence"])
            self.data["user_facts"] = self.data["user_facts"][-200:]
        self.save()

    def add_preference(self, category: str, preference: str) -> None:
        """Add a user preference in a category."""
        if category not in self.data["preferences"]:
            self.data["preferences"][category] = []
        if preference not in self.data["preferences"][category]:
            self.data["preferences"][category].append(preference)
        self.save()

    def add_dislike(self, item: str) -> None:
        """Record what the user doesn't like."""
        if item not in self.data["dislikes"]:
            self.data["dislikes"].append(item)
        self.save()

    def bump_topic(self, topic: str) -> None:
        """Increment topic frequency counter. Auto-saves every 10 bumps (BUG-H2 FIX)."""
        if topic not in self.data["topics"]:
            self.data["topics"][topic] = {"count": 0, "last_seen": None}
        self.data["topics"][topic]["count"] += 1
        self.data["topics"][topic]["last_seen"] = datetime.now().isoformat()
        self._dirty = True
        # BUG-H2 FIX: auto-save every 10 bumps to prevent data loss on crash
        self._bump_count += 1
        if self._bump_count >= 10:
            self.save()
            self._bump_count = 0

    def flush(self) -> None:
        """Save if there are unsaved topic bumps."""
        if self._dirty:
            self.save()

    def add_project(self, name: str, description: str = "") -> None:
        """Track a project the user is working on."""
        names = [p["name"] for p in self.data["projects"]]
        if name not in names:
            self.data["projects"].append({
                "name": name,
                "description": description,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            })
        else:
            for p in self.data["projects"]:
                if p["name"] == name:
                    p["last_seen"] = datetime.now().isoformat()
        self.save()

    def update_communication_style(self, key: str, value: str) -> None:
        """Update how the user likes to communicate."""
        self.data["communication_style"][key] = value
        self.save()

    def add_custom_note(self, note: str) -> None:
        """Manually added note by the user."""
        self.data["custom_notes"].append({
            "note": note,
            "added_at": datetime.now().isoformat(),
        })
        self.save()

    def mark_trained(self, interactions_this_session: int) -> None:
        """Called after /train completes."""
        self.data["last_trained"] = datetime.now().isoformat()
        self.data["sessions_trained"] = self.data.get("sessions_trained", 0) + 1
        self.data["total_interactions"] = (
            self.data.get("total_interactions", 0) + interactions_this_session
        )
        self.save()

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_top_topics(self, n: int = 10) -> List[Dict]:
        """Return most discussed topics sorted by frequency."""
        topics = [
            {"topic": k, **v}
            for k, v in self.data["topics"].items()
        ]
        topics.sort(key=lambda x: x["count"], reverse=True)
        return topics[:n]

    def get_facts_summary(self, n: int = 20) -> str:
        """Get a readable summary of learned facts."""
        facts = sorted(
            self.data["user_facts"],
            key=lambda x: x["confidence"],
            reverse=True
        )[:n]
        if not facts:
            return "No facts learned yet."
        lines = []
        for f in facts:
            conf = f["confidence"]
            conf_label = "✓✓" if conf >= 0.9 else "✓" if conf >= 0.6 else "?"
            lines.append(f"  {conf_label} {f['fact']}")
        return "\n".join(lines)

    def search(self, query: str) -> str:
        """Search all learnings for a keyword."""
        results = []
        q = query.lower()

        for f in self.data["user_facts"]:
            if q in f["fact"].lower():
                results.append(f"[FACT] {f['fact']}")

        for cat, prefs in self.data["preferences"].items():
            for p in prefs:
                if q in p.lower() or q in cat.lower():
                    results.append(f"[PREF:{cat}] {p}")

        for item in self.data["dislikes"]:
            if q in item.lower():
                results.append(f"[DISLIKE] {item}")

        for proj in self.data["projects"]:
            if q in proj["name"].lower() or q in proj.get("description", "").lower():
                results.append(f"[PROJECT] {proj['name']}: {proj.get('description', '')}")

        for note in self.data["custom_notes"]:
            if q in note["note"].lower():
                results.append(f"[NOTE] {note['note']}")

        return "\n".join(results[:20]) if results else f"No learnings found for: {query}"

    def to_context_string(self, max_facts: int = 15) -> str:
        """Build a compact context string for the LLM system prompt."""
        parts = []

        # Top facts
        facts = sorted(
            self.data["user_facts"],
            key=lambda x: x["confidence"],
            reverse=True
        )[:max_facts]
        if facts:
            parts.append("USER FACTS:\n" + "\n".join(f"  • {f['fact']}" for f in facts))

        # Top topics
        top = self.get_top_topics(5)
        if top:
            parts.append("MAIN INTERESTS: " + ", ".join(t["topic"] for t in top))

        # Projects
        if self.data["projects"]:
            proj_names = [p["name"] for p in self.data["projects"][-5:]]
            parts.append("ACTIVE PROJECTS: " + ", ".join(proj_names))

        # Preferences (compact)
        if self.data["preferences"]:
            for cat, prefs in list(self.data["preferences"].items())[:5]:
                parts.append(f"PREFERS ({cat}): {', '.join(prefs[:3])}")

        # Dislikes
        if self.data["dislikes"]:
            parts.append("DISLIKES: " + ", ".join(self.data["dislikes"][:5]))

        # Communication style
        if self.data["communication_style"]:
            for k, v in self.data["communication_style"].items():
                parts.append(f"COMM STYLE ({k}): {v}")

        return "\n".join(parts) if parts else ""

    def stats_summary(self) -> str:
        """One-line stats."""
        facts = len(self.data["user_facts"])
        topics = len(self.data["topics"])
        projects = len(self.data["projects"])
        trained = self.data.get("sessions_trained", 0)
        total = self.data.get("total_interactions", 0)
        return (
            f"{facts} facts · {topics} topics · {projects} projects · "
            f"{trained} training sessions · {total} total interactions"
        )
