"""
Lirox v2.0 — Self-Learning System

Continuous improvement from:
- Execution results
- User feedback
- Mistake patterns
- Success patterns
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Lesson:
    """A learned lesson from an execution."""
    task:    str
    outcome: str           # "success" | "failure"
    reason:  str           = ""
    tags:    List[str]     = field(default_factory=list)
    ts:      float         = field(default_factory=time.time)


class KnowledgeBase:
    """In-memory (optionally persistent) knowledge store."""

    def __init__(self, storage_file: Optional[str] = None):
        self._lessons:  List[Lesson]        = []
        self._facts:    List[str]           = []
        self._preferences: Dict[str, Any]  = {}
        self._storage   = storage_file
        if storage_file and os.path.exists(storage_file):
            self._load()

    def add(self, lesson: Lesson) -> None:
        self._lessons.append(lesson)
        self._persist()

    def get_lessons(self, outcome: Optional[str] = None) -> List[Lesson]:
        if outcome:
            return [l for l in self._lessons if l.outcome == outcome]
        return list(self._lessons)

    def add_preference(self, key: str, value: Any) -> None:
        self._preferences[key] = value
        self._persist()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._preferences.get(key, default)

    def _persist(self) -> None:
        if not self._storage:
            return
        try:
            data = {
                "lessons": [
                    {"task": l.task, "outcome": l.outcome, "reason": l.reason, "tags": l.tags}
                    for l in self._lessons
                ],
                "preferences": self._preferences,
            }
            with open(self._storage, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load(self) -> None:
        try:
            with open(self._storage, "r", encoding="utf-8") as f:
                data = json.load(f)
            for l in data.get("lessons", []):
                self._lessons.append(Lesson(**l))
            self._preferences = data.get("preferences", {})
        except Exception:
            pass


class SelfLearningSystem:
    """
    Learns continuously from task execution results and user feedback.

    Usage:
        learner = SelfLearningSystem()
        learner.learn_from_execution("Sort a list", {"status": "success", "output": [1,2,3]})
        learner.adapt_to_user("I prefer shorter responses")
    """

    def __init__(self, storage_file: Optional[str] = None):
        self.knowledge_base = KnowledgeBase(storage_file)
        self._success_counts: Dict[str, int] = {}
        self._failure_counts: Dict[str, int] = {}
        self._improvements:   List[str]      = []

    # ── Learning ──────────────────────────────────────────────────────────────

    def learn_from_execution(self, task: str, result: Dict[str, Any]) -> None:
        """Learn from a completed task execution."""
        success = result.get("status") == "success"
        outcome = "success" if success else "failure"
        reason  = result.get("error", "") if not success else ""

        lesson = Lesson(task=task, outcome=outcome, reason=reason, tags=self._tag(task))
        self.knowledge_base.add(lesson)
        self.track_success_rate(task, success)
        self.plan_improvements(task, result)

    def track_success_rate(self, task: str, success: bool) -> None:
        """Update success/failure counters for a task category."""
        category = self._categorize(task)
        if success:
            self._success_counts[category] = self._success_counts.get(category, 0) + 1
        else:
            self._failure_counts[category] = self._failure_counts.get(category, 0) + 1

    def plan_improvements(self, task: str, result: Dict[str, Any]) -> None:
        """Generate improvement notes from a task result."""
        if result.get("status") != "success":
            error = result.get("error", "unknown error")
            self._improvements.append(f"Improve handling of: {error} (task: {task[:50]})")

    def adapt_to_user(self, user_feedback: str) -> None:
        """Parse and store user preferences from feedback."""
        preference = self._parse_preference(user_feedback)
        for key, value in preference.items():
            self.knowledge_base.add_preference(key, value)

    # ── Self-Improvement ──────────────────────────────────────────────────────

    def get_improvements(self) -> List[str]:
        """Return all pending improvement notes."""
        return list(self._improvements)

    def get_success_rate(self, category: str) -> float:
        """Return success rate (0.0–1.0) for a task category."""
        s = self._success_counts.get(category, 0)
        f = self._failure_counts.get(category, 0)
        total = s + f
        return s / total if total > 0 else 0.0

    def summarize(self) -> Dict[str, Any]:
        """Return a summary of what has been learned."""
        lessons = self.knowledge_base.get_lessons()
        successes = sum(1 for l in lessons if l.outcome == "success")
        return {
            "total_lessons":   len(lessons),
            "successes":       successes,
            "failures":        len(lessons) - successes,
            "improvements":    len(self._improvements),
            "preferences":     dict(self.knowledge_base._preferences),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _tag(self, task: str) -> List[str]:
        tags = []
        task_lower = task.lower()
        if any(w in task_lower for w in ["file", "write", "read"]):
            tags.append("file_io")
        if any(w in task_lower for w in ["search", "browse", "fetch"]):
            tags.append("web")
        if any(w in task_lower for w in ["code", "function", "class"]):
            tags.append("code")
        return tags

    def _categorize(self, task: str) -> str:
        task_lower = task.lower()
        if "file" in task_lower:
            return "file_io"
        if "search" in task_lower or "browse" in task_lower:
            return "web"
        if "code" in task_lower:
            return "code"
        return "general"

    def _parse_preference(self, feedback: str) -> Dict[str, Any]:
        feedback_lower = feedback.lower()
        prefs = {}
        if "short" in feedback_lower or "concise" in feedback_lower:
            prefs["response_length"] = "short"
        elif "detail" in feedback_lower or "verbose" in feedback_lower:
            prefs["response_length"] = "verbose"
        if "formal" in feedback_lower:
            prefs["tone"] = "formal"
        elif "casual" in feedback_lower or "friendly" in feedback_lower:
            prefs["tone"] = "casual"
        return prefs
