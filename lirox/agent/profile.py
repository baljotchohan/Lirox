"""
Lirox v2.0 — User Profile System (CLI-First)

Storage anchored to PROJECT_ROOT (not CWD).
v2.0: Advanced prompt system with learning context boost integration.
"""

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
        "user_context":    "",
        "preferences":     {},
        "learned_facts":   [],
        "created_at":      None,
        "last_updated":    None,
    }

    def __init__(self, storage_file: str = None):
        if storage_file is None:
            storage_file = os.path.join(PROJECT_ROOT, "profile.json")
        self.storage_file = storage_file
        self._lock = threading.Lock() # Initialize the lock
        self.data = self._load()

    def _load(self):
        with self._lock: # [FIX #2] Lock during reads
            if os.path.exists(self.storage_file):
                try:
                    with open(self.storage_file, "r") as f:
                        data = json.load(f)
                        merged = dict(self.DEFAULT)
                        merged.update(data)
                        return merged
                except (json.JSONDecodeError, IOError) as e:
                    from lirox.utils.structured_logger import get_logger
                    get_logger("lirox.profile").warning(f"Non-critical error: {e}")
            
            profile = dict(self.DEFAULT)
            profile["created_at"] = datetime.now().isoformat()
            return profile

    def save(self):
        """Saves profile data to disk safely across multiple threads."""
        with self._lock: # Acquire lock before opening file
            temp_file = self.storage_file + ".tmp"
            try:
                self.data["last_updated"] = datetime.now().isoformat()
                with open(temp_file, "w") as f:
                    json.dump(self.data, f, indent=4)
                # [FIX #2] Atomic file replacement
                os.replace(temp_file, self.storage_file)
            except Exception as e:
                from lirox.utils.structured_logger import get_logger
                get_logger("lirox.profile").warning(f"Non-critical error saving profile: {e}")
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError as e2:
                        get_logger("lirox.profile").warning(f"Non-critical error removing temp file: {e2}")

    def update(self, key: str, value):
        with self._lock:
            self.data[key] = value
        self.save()

    def add_learned_fact(self, fact: str):
        with self._lock:
            if fact not in self.data["learned_facts"]:
                self.data["learned_facts"].append(fact)
                if len(self.data["learned_facts"]) > 50:
                    self.data["learned_facts"] = self.data["learned_facts"][-50:]
        self.save()

    def add_goal(self, goal: str):
        if not goal:
            return
        with self._lock:
            if "goals" not in self.data:
                self.data["goals"] = []
            if goal not in self.data["goals"]:
                self.data["goals"].append(goal)
        self.save()

    def add_learned_preference(self, category: str, preference: str):
        """Learn user preferences over time."""
        with self._lock:
            if "preferences" not in self.data:
                self.data["preferences"] = {}
            if category not in self.data["preferences"]:
                self.data["preferences"][category] = []
            if preference not in self.data["preferences"][category]:
                self.data["preferences"][category].append(preference)
                if len(self.data["preferences"][category]) > 20:
                    self.data["preferences"][category] = \
                        self.data["preferences"][category][-20:]
        self.save()

    def track_task_execution(self, task_description: str, success: bool,
                             duration_seconds: float):
        """Track what tasks the user typically runs."""
        with self._lock:
            if "task_history" not in self.data:
                self.data["task_history"] = []
            self.data["task_history"].append({
                "task": task_description[:100],
                "success": success,
                "duration": duration_seconds,
                "timestamp": datetime.now().isoformat(),
            })
            if len(self.data["task_history"]) > 100:
                self.data["task_history"] = self.data["task_history"][-100:]
        self.save()

    def get_dominant_topics(self) -> list:
        """Identify topics user is most interested in."""
        if "learned_facts" not in self.data:
            return []
        
        facts = self.data["learned_facts"][-30:]
        
        from collections import Counter
        words = []
        for fact in facts:
            words.extend(fact.lower().split())
        
        stop_words = {"the", "a", "is", "are", "to", "and", "or", "of", "in", "for", "this", "that"}
        meaningful = [w for w in words if w not in stop_words and len(w) > 3]
        
        counter = Counter(meaningful)
        return [word for word, _ in counter.most_common(5)]

    # BUG-5 FIX: Removed to_advanced_system_prompt() — was never called in the active code
    # path (soul.to_system_prompt() is used instead) and contained stale "jarves" references.

    # BUG-5 FIX: Removed to_system_prompt() — was never called in the active code path
    # (soul.to_system_prompt() is used instead) and contained stale "jarves" references.

    def is_setup(self) -> bool:
        return bool(
            self.data.get("user_name") and
            self.data["user_name"] not in ("Operator", self.DEFAULT["user_name"])
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
