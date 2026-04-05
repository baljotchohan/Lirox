"""Lirox v2.0 — Task Scheduler

Lightweight scheduler for recording and managing deferred tasks.
Tasks are persisted to a JSON file so they survive process restarts.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskScheduler:
    """
    Simple task queue with JSON persistence.

    Parameters
    ----------
    storage_file:
        Path to the JSON file used for persistence.
        Defaults to ``data/tasks.json`` relative to the working directory.
    """

    def __init__(self, storage_file: str = "data/tasks.json"):
        self.storage_file = storage_file
        self.tasks: List[Dict[str, Any]] = []
        self._next_id: int = 1
        if os.path.exists(storage_file):
            self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def schedule_task(self, goal: str, schedule: str = "now") -> Dict[str, Any]:
        """
        Add a new task and return it.

        Parameters
        ----------
        goal:     Human-readable description of what to accomplish.
        schedule: When to run (e.g. "in_5_minutes", "daily", "now").
        """
        task: Dict[str, Any] = {
            "id": self._next_id,
            "goal": goal,
            "schedule": schedule,
            "status": "scheduled",
        }
        self.tasks.append(task)
        self._next_id += 1
        self._save()
        return task

    def cancel_task(self, task_id: int) -> str:
        """Mark a task as cancelled. Returns a status message."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "cancelled"
                self._save()
                return f"Task {task_id} cancelled."
        return f"Task {task_id} not found."

    def list_tasks(self, status_filter: Optional[str] = None) -> str:
        """Return a human-readable listing of tasks, optionally filtered by status."""
        tasks = self.tasks
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]

        if not tasks:
            return "No tasks scheduled."

        lines = []
        for t in tasks:
            lines.append(f"  [{t['id']}] ({t['status']}) {t['goal']} — {t['schedule']}")
        return "\n".join(lines)

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Return a specific task by ID, or None if not found."""
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        return None

    def clear_completed(self) -> None:
        """Remove all completed or cancelled tasks."""
        self.tasks = [t for t in self.tasks if t["status"] == "scheduled"]
        self._save()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        Path(self.storage_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_file, "w", encoding="utf-8") as fh:
            json.dump({"next_id": self._next_id, "tasks": self.tasks}, fh, indent=2)

    def _load(self) -> None:
        try:
            with open(self.storage_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self.tasks = data.get("tasks", [])
                self._next_id = data.get("next_id", len(self.tasks) + 1)
        except (json.JSONDecodeError, OSError):
            self.tasks = []
            self._next_id = 1
