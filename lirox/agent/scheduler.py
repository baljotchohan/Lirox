"""
Lirox v0.3 — Task Scheduler

Session-level background task scheduling:
- Schedule tasks to run at specific times or intervals
- List and cancel scheduled tasks
- Runs in a daemon thread (dies when Lirox exits)
- Persists task definitions to disk for display
"""

import json
import os
import time
import threading
from datetime import datetime, timedelta

try:
    import schedule
except ImportError:
    schedule = None


class TaskScheduler:
    """Background task scheduler for deferred execution."""

    def __init__(self, storage_file="scheduled_tasks.json"):
        self.storage_file = storage_file
        self.tasks = self._load()
        self._running = False
        self._thread = None
        self._next_id = max((t["id"] for t in self.tasks), default=0) + 1
        # Callback for executing tasks — set by core.py
        self.execute_callback = None

    def _load(self):
        """Load saved tasks from disk."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        """Persist tasks to disk."""
        with open(self.storage_file, 'w') as f:
            json.dump(self.tasks, f, indent=4)

    def schedule_task(self, goal, when="in_5_minutes"):
        """
        Schedule a task to run later.

        Args:
            goal: The task goal string
            when: Timing string — supports:
                  "in_5_minutes", "in_10_minutes", "in_30_minutes",
                  "in_1_hour", "daily_9am", "daily_6pm"

        Returns:
            Task dict with ID and scheduled time
        """
        if not schedule:
            return {
                "id": -1,
                "error": "schedule library not installed. Run: pip install schedule"
            }

        task = {
            "id": self._next_id,
            "goal": goal,
            "when": when,
            "status": "scheduled",
            "created_at": datetime.now().isoformat(),
            "scheduled_for": self._resolve_time(when),
        }

        self._next_id += 1
        self.tasks.append(task)
        self._save()

        # Register with schedule library
        self._register_task(task)

        # Start background thread if not already running
        if not self._running:
            self.run_background()

        return task

    def _resolve_time(self, when):
        """Convert a 'when' string to an ISO timestamp."""
        now = datetime.now()

        time_map = {
            "in_5_minutes": now + timedelta(minutes=5),
            "in_10_minutes": now + timedelta(minutes=10),
            "in_30_minutes": now + timedelta(minutes=30),
            "in_1_hour": now + timedelta(hours=1),
            "in_2_hours": now + timedelta(hours=2),
        }

        if when in time_map:
            return time_map[when].isoformat()

        # For daily schedules, return the description
        if when.startswith("daily_"):
            return f"Daily at {when.replace('daily_', '')}"

        return now.isoformat()

    def _register_task(self, task):
        """Register a task with the schedule library."""
        if not schedule:
            return

        when = task["when"]
        task_id = task["id"]

        def run_task():
            self._execute_task(task_id)

        if when == "in_5_minutes":
            # One-shot: run after delay in the background thread
            threading.Timer(300, run_task).start()
        elif when == "in_10_minutes":
            threading.Timer(600, run_task).start()
        elif when == "in_30_minutes":
            threading.Timer(1800, run_task).start()
        elif when == "in_1_hour":
            threading.Timer(3600, run_task).start()
        elif when == "in_2_hours":
            threading.Timer(7200, run_task).start()
        elif when == "daily_9am":
            schedule.every().day.at("09:00").do(run_task).tag(f"task_{task_id}")
        elif when == "daily_6pm":
            schedule.every().day.at("18:00").do(run_task).tag(f"task_{task_id}")

    def _execute_task(self, task_id):
        """Execute a scheduled task by ID."""
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return

        task["status"] = "running"
        self._save()

        if self.execute_callback:
            try:
                self.execute_callback(task["goal"])
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
            except Exception as e:
                task["status"] = "failed"
                task["error"] = str(e)
        else:
            task["status"] = "failed"
            task["error"] = "No execute callback registered"

        self._save()

    def list_tasks(self):
        """
        Format all scheduled tasks for display.

        Returns:
            Formatted string of all tasks
        """
        if not self.tasks:
            return "No scheduled tasks."

        lines = ["📅 SCHEDULED TASKS", ""]
        for task in self.tasks:
            icon = {
                "scheduled": "⏳",
                "running": "⚙️",
                "completed": "✓",
                "failed": "✗",
                "cancelled": "⊘"
            }.get(task["status"], "?")

            lines.append(f"  {icon} [{task['id']}] {task['goal'][:50]}")
            lines.append(f"    When: {task['when']} | Status: {task['status']}")
            lines.append(f"    Scheduled for: {task.get('scheduled_for', 'N/A')}")
            lines.append("")

        return "\n".join(lines)

    def cancel_task(self, task_id):
        """
        Cancel a scheduled task.

        Args:
            task_id: ID of the task to cancel

        Returns:
            Success/failure message
        """
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return f"Task #{task_id} not found."

        if task["status"] == "completed":
            return f"Task #{task_id} already completed."

        task["status"] = "cancelled"
        self._save()

        # Remove from schedule library
        if schedule:
            schedule.clear(f"task_{task_id}")

        return f"Task #{task_id} cancelled."

    def run_background(self):
        """Start the background scheduler thread."""
        if self._running:
            return

        self._running = True

        def worker():
            while self._running:
                if schedule:
                    schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds

        self._thread = threading.Thread(target=worker, daemon=True, name="lirox-scheduler")
        self._thread.start()

    def stop(self):
        """Stop the background scheduler."""
        self._running = False
