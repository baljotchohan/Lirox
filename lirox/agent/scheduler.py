"""
Lirox v2.0 — Task Scheduler

Schedule, list, and cancel future tasks.
Persists task queue to a JSON file.
"""

from __future__ import annotations

import json
import os
from typing import List, Dict, Any


class TaskScheduler:
    """
    Simple task scheduler: add goals with a time label, list them, cancel them.
    """

    def __init__(self, storage_file: str = "tasks.json"):
        self.storage_file = storage_file
        self.tasks: List[Dict[str, Any]] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.tasks = data
            except Exception:
                self.tasks = []

    def _save(self) -> None:
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Core API ──────────────────────────────────────────────────────────────

    def schedule_task(self, goal: str, when: str) -> Dict[str, Any]:
        """
        Schedule a new task.

        Args:
            goal: Description of what to do.
            when: Human-readable time spec (e.g. "in_5_minutes").

        Returns:
            Task dict with id, goal, when, status.
        """
        task_id = len(self.tasks) + 1
        task = {
            "id":     task_id,
            "goal":   goal,
            "when":   when,
            "status": "scheduled",
        }
        self.tasks.append(task)
        self._save()
        return task

    def list_tasks(self) -> str:
        """Return a human-readable listing of all tasks."""
        if not self.tasks:
            return "No tasks scheduled."
        lines = ["Scheduled Tasks:"]
        for task in self.tasks:
            status = task.get("status", "unknown")
            lines.append(
                f"  [{task['id']}] {task['goal']} — {task.get('when', '')} ({status})"
            )
        return "\n".join(lines)

    def cancel_task(self, task_id: int) -> str:
        """Cancel a task by ID. Returns confirmation message."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "cancelled"
                self._save()
                return f"Task {task_id} has been cancelled."
        return f"Task {task_id} not found."

    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get a specific task by ID."""
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        return {}
