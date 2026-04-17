"""Lirox v2.0.0 — Unified Memory System

Combines LearningsStore (persistent knowledge) and MemoryManager (exchange log)
into a single, thread-safe module.

BUG-1 FIX: Removed staged-patch system. LearningsStore no longer crashes on
missing keys — uses .get() with defaults everywhere.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.config import MEMORY_DIR, DATA_DIR


# ─── LearningsStore ──────────────────────────────────────────────────────────

class LearningsStore:
    """Persistent knowledge base extracted from conversations."""

    _DEFAULTS: Dict[str, Any] = {
        "facts":               [],
        "topics":              [],
        "projects":            [],
        "communication_style": {},
        "last_trained":        None,
        "total_extractions":   0,
    }

    def __init__(self, path: str = None):
        if path is None:
            path = os.path.join(DATA_DIR, "learnings.json")
        self.path  = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                merged = dict(self._DEFAULTS)
                merged.update(raw)
                # BUG-1 FIX: ensure all keys exist even if file is partial
                for k, v in self._DEFAULTS.items():
                    if k not in merged:
                        merged[k] = v if not isinstance(v, list) else list(v)
                return merged
            except (json.JSONDecodeError, IOError):
                pass
        return {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                for k, v in self._DEFAULTS.items()}

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_facts(self) -> List[str]:
        with self._lock:
            return list(self._data.get("facts", []))

    def get_topics(self) -> List[str]:
        with self._lock:
            return list(self._data.get("topics", []))

    def get_projects(self) -> List[str]:
        with self._lock:
            return list(self._data.get("projects", []))

    def get_communication_style(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._data.get("communication_style", {}))

    def get_context_string(self) -> str:
        """Build a formatted string of all learnings for LLM context injection."""
        with self._lock:
            facts   = self._data.get("facts", [])[-20:]
            topics  = self._data.get("topics", [])[-10:]
            projs   = self._data.get("projects", [])[-5:]
            style   = self._data.get("communication_style", {})

        parts = []
        if facts:
            parts.append("Known facts:\n" + "\n".join(f"  • {f}" for f in facts))
        if topics:
            parts.append("Interests: " + ", ".join(topics))
        if projs:
            parts.append("Projects: " + ", ".join(projs))
        if style:
            style_items = ", ".join(f"{k}: {v}" for k, v in list(style.items())[:5])
            parts.append(f"Communication style: {style_items}")
        return "\n".join(parts)

    def summary_dict(self) -> dict:
        with self._lock:
            return {
                "facts":   len(self._data.get("facts", [])),
                "topics":  len(self._data.get("topics", [])),
                "projects": len(self._data.get("projects", [])),
                "last_trained": self._data.get("last_trained", "never"),
            }

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_fact(self, fact: str) -> bool:
        if not fact or not fact.strip():
            return False
        fact = fact.strip()
        with self._lock:
            existing = self._data.get("facts", [])
            # Dedup by normalized text
            normalized = fact.lower().strip(".,!?")
            for f in existing:
                if f.lower().strip(".,!?") == normalized:
                    return False
            existing.append(fact)
            self._data["facts"] = existing[-200:]
        self._save()
        return True

    def add_topic(self, topic: str) -> None:
        if not topic:
            return
        topic = topic.strip()
        with self._lock:
            topics = self._data.get("topics", [])
            if topic not in topics:
                topics.append(topic)
                self._data["topics"] = topics[-50:]
        self._save()

    def add_project(self, project: str) -> None:
        if not project:
            return
        project = project.strip()
        with self._lock:
            projects = self._data.get("projects", [])
            if project not in projects:
                projects.append(project)
                self._data["projects"] = projects[-20:]
        self._save()

    def update_communication_style(self, style_dict: Dict[str, str]) -> None:
        with self._lock:
            existing = self._data.get("communication_style", {})
            existing.update(style_dict)
            self._data["communication_style"] = existing
        self._save()

    def merge_extracted(self, extracted: Dict[str, Any]) -> dict:
        """Merge a batch of extracted knowledge. Returns counts of what was added."""
        counts = {"facts": 0, "topics": 0, "projects": 0}
        for fact in extracted.get("facts", []):
            if self.add_fact(fact):
                counts["facts"] += 1
        for topic in extracted.get("topics", []):
            self.add_topic(topic)
            counts["topics"] += 1
        for project in extracted.get("projects", []):
            self.add_project(project)
            counts["projects"] += 1
        if extracted.get("communication_style"):
            self.update_communication_style(extracted["communication_style"])
        with self._lock:
            self._data["last_trained"]      = datetime.now().isoformat()
            self._data["total_extractions"] = self._data.get("total_extractions", 0) + 1
        self._save()
        return counts

    def clear(self) -> None:
        with self._lock:
            self._data = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                          for k, v in self._DEFAULTS.items()}
        self._save()

    def export_json(self) -> str:
        with self._lock:
            return json.dumps(self._data, indent=2)

    def import_json(self, raw: str) -> bool:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return False
        if not isinstance(parsed, dict):
            return False
        self.merge_extracted(parsed)
        return True


# ─── MemoryManager ───────────────────────────────────────────────────────────

class MemoryManager:
    """Manages conversation exchange log (JSONL) for training and recall."""

    def __init__(self, log_path: str = None):
        if log_path is None:
            log_path = os.path.join(MEMORY_DIR, "exchanges.jsonl")
        self.log_path = log_path
        self._lock    = threading.Lock()

    def save_exchange(self, user_msg: str, assistant_msg: str) -> None:
        entry = {
            "ts":        datetime.now().isoformat(),
            "user":      user_msg[:2000],
            "assistant": assistant_msg[:2000],
        }
        with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                pass

    def load_recent(self, n: int = 30) -> List[Dict[str, str]]:
        entries = []
        if not os.path.exists(self.log_path):
            return entries
        with self._lock:
            try:
                lines = Path(self.log_path).read_text(encoding="utf-8").splitlines()
            except Exception:
                return entries
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def count_exchanges(self) -> int:
        if not os.path.exists(self.log_path):
            return 0
        with self._lock:
            try:
                lines = Path(self.log_path).read_text(encoding="utf-8").splitlines()
                return sum(1 for l in lines if l.strip())
            except Exception:
                return 0

    def format_for_training(self, n: int = 50) -> str:
        entries = self.load_recent(n)
        if not entries:
            return ""
        parts = []
        for e in entries:
            parts.append(f"User: {e.get('user', '')}")
            parts.append(f"Assistant: {e.get('assistant', '')}")
        return "\n".join(parts)
