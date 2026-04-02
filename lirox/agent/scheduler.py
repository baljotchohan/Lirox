"""
Lirox v0.5 — Task Scheduler

Session-level background task scheduling.
Storage anchored to PROJECT_ROOT (not CWD).
"""

import json
import os
import time
import threading
from datetime import datetime, timedelta
from lirox.config import PROJECT_ROOT

try:
    import schedule
except ImportError:
    schedule = None


class TaskScheduler:
    """Background task scheduler for deferred execution."""

    def __init__(self, storage_file: str = None):
        if storage_file is None:
            storage_file = os.path.join(PROJECT_ROOT, "scheduled_tasks.json")
        self.storage_file = storage_file
        self.tasks = self._load()
        self._running = False
        self._thread = None
        self._next_id = max((t["id"] for t in self.tasks), default=0) + 1
        self.execute_callback = None
        
        # [FIX #5] Restore loaded persisted tasks effectively
        for task in self.tasks:
            if task.get("status") == "scheduled":
                self._register_task(task)

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        with open(self.storage_file, "w") as f:
            json.dump(self.tasks, f, indent=4)

    def schedule_task(self, goal: str, when: str = "in_5_minutes") -> dict:
        if not schedule:
            return {"id": -1, "error": "schedule library not installed. Run: pip install schedule"}

        task = {
            "id":            self._next_id,
            "goal":          goal,
            "when":          when,
            "status":        "scheduled",
            "created_at":    datetime.now().isoformat(),
            "scheduled_for": self._resolve_time(when),
        }
        self._next_id += 1
        self.tasks.append(task)
        self._save()
        self._register_task(task)

        if not self._running:
            self.run_background()

        return task

    def _resolve_time(self, when: str) -> str:
        now = datetime.now()
        time_map = {
            "in_5_minutes":  now + timedelta(minutes=5),
            "in_10_minutes": now + timedelta(minutes=10),
            "in_30_minutes": now + timedelta(minutes=30),
            "in_1_hour":     now + timedelta(hours=1),
            "in_2_hours":    now + timedelta(hours=2),
        }
        if when in time_map:
            return time_map[when].isoformat()
        if when.startswith("daily_"):
            return f"Daily at {when.replace('daily_', '')}"
        return now.isoformat()

    def _register_task(self, task: dict):
        if not schedule:
            return
        when     = task["when"]
        task_id  = task["id"]

        def run_task():
            self._execute_task(task_id)

        timers = {
            "in_5_minutes":  300,
            "in_10_minutes": 600,
            "in_30_minutes": 1800,
            "in_1_hour":     3600,
            "in_2_hours":    7200,
        }
        if when in timers:
            threading.Timer(timers[when], run_task).start()
        elif when == "daily_9am":
            schedule.every().day.at("09:00").do(run_task).tag(f"task_{task_id}")
        elif when == "daily_6pm":
            schedule.every().day.at("18:00").do(run_task).tag(f"task_{task_id}")

    def _execute_task(self, task_id: int):
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return

        task["status"] = "running"
        self._save()

        if self.execute_callback:
            try:
                # v0.6: Pass the entire task for better context if needed
                self.execute_callback(task["goal"])
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
            except Exception as e:
                task["status"] = "failed"
                task["error"]  = f"Execution Error: {str(e)}"
        else:
            task["status"] = "failed"
            task["error"]  = "Kernel Initialization Failure: Execute callback (process_task) not registered."
            # v0.6: Keep it as failed so it can be manually re-queued or audited
        
        self._save()

    def list_tasks(self) -> str:
        if not self.tasks:
            return "No scheduled tasks."

        lines = ["📅 SCHEDULED TASKS", ""]
        for task in self.tasks:
            icon = {
                "scheduled": "⏳", "running": "⚙️",
                "completed": "✓",  "failed":  "✗", "cancelled": "⊘"
            }.get(task["status"], "?")
            lines.append(f"  {icon} [{task['id']}] {task['goal'][:50]}")
            lines.append(f"    When: {task['when']} | Status: {task['status']}")
            lines.append(f"    Scheduled for: {task.get('scheduled_for', 'N/A')}")
            lines.append("")
        return "\n".join(lines)

    def cancel_task(self, task_id: int) -> str:
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return f"Task #{task_id} not found."
        if task["status"] == "completed":
            return f"Task #{task_id} already completed."

        task["status"] = "cancelled"
        self._save()

        if schedule:
            schedule.clear(f"task_{task_id}")

        return f"Task #{task_id} cancelled."

    def run_background(self):
        if self._running:
            return
        self._running = True

        def worker():
            while self._running:
                if schedule:
                    schedule.run_pending()
                time.sleep(30)

        self._thread = threading.Thread(target=worker, daemon=True, name="lirox-scheduler")
        self._thread.start()

    def stop(self):
        self._running = False
