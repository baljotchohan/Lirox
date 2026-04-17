"""Lirox v2.0.0 — User Profile System"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime

from lirox.config import PROJECT_ROOT


class UserProfile:
    DEFAULT = {
        "agent_name":      "Lirox",
        "user_name":       "Operator",
        "niche":           "Generalist",
        "profession":      "Developer",
        "current_project": "",
        "goals":           [],
        "tone":            "direct",
        "format_preference": "balanced",
        "user_context":    "",
        "preferences":     {},
        "created_at":      None,
        "last_updated":    None,
    }

    def __init__(self, storage_file: str = None):
        if storage_file is None:
            storage_file = os.path.join(PROJECT_ROOT, "profile.json")
        self.storage_file = storage_file
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        with self._lock:
            if os.path.exists(self.storage_file):
                try:
                    with open(self.storage_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    merged = dict(self.DEFAULT)
                    merged.update(data)
                    return merged
                except (json.JSONDecodeError, IOError):
                    pass
            profile = dict(self.DEFAULT)
            profile["created_at"] = datetime.now().isoformat()
            return profile

    def save(self) -> None:
        with self._lock:
            temp_file = self.storage_file + ".tmp"
            try:
                self.data["last_updated"] = datetime.now().isoformat()
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                os.replace(temp_file, self.storage_file)
            except Exception:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

    def update(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value
        self.save()

    def add_goal(self, goal: str) -> None:
        if not goal:
            return
        with self._lock:
            if "goals" not in self.data:
                self.data["goals"] = []
            if goal not in self.data["goals"]:
                self.data["goals"].append(goal)
        self.save()

    def is_setup(self) -> bool:
        return bool(
            self.data.get("user_name")
            and self.data["user_name"] not in ("Operator", self.DEFAULT["user_name"])
        )

    def summary(self) -> str:
        d = self.data
        lines = [
            f"  Name           : {d.get('user_name', '-')}",
            f"  Agent          : {d.get('agent_name', 'Lirox')}",
            f"  Work           : {d.get('niche', '-')}",
            f"  Current Project: {d.get('current_project', '-')}",
            f"  Profession     : {d.get('profession', '-')}",
            f"  Tone           : {d.get('tone', '-')}",
        ]
        if d.get("goals"):
            lines.append(f"  Goals          : {', '.join(d['goals'][:3])}")
        return "\n".join(lines)
