"""Lirox v2.0 — Agent Planner

Converts a natural-language goal into a structured, step-by-step execution plan.
LLM calls are injectable via `generate_response` for easy mocking in tests.
"""

import json
import re
from typing import Dict, Any, Optional

from lirox.utils.llm import generate_response

_PLAN_SYSTEM = (
    "You are a task planner. Convert the user goal into a JSON execution plan.\n"
    "Return ONLY valid JSON with this exact structure:\n"
    '{"goal": "...", "steps": [{"id": 1, "task": "...", "tools": ["..."], '
    '"depends_on": [], "expected_output": "..."}], '
    '"estimated_time": "...", "tools_required": [...]}'
)

# Keywords for heuristic tool guessing
_TERMINAL_KEYWORDS = ["install", "pip", "npm", "run", "execute", "script", "terminal", "command", "build", "compile", "test", "pytest"]
_BROWSER_KEYWORDS = ["search", "web", "fetch", "url", "browse", "scrape", "website", "internet", "online", "lookup", "google"]
_FILE_KEYWORDS = ["write", "save", "read", "file", "disk", "output", "create", "store", "append"]


class Planner:
    """Structured plan generator for multi-step task execution."""

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self._last_plan: Optional[Dict[str, Any]] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def create_plan(self, goal: str) -> Dict[str, Any]:
        """
        Call the LLM and return a structured plan dict.
        Falls back to parsing a numbered-list response when JSON is unavailable.
        """
        raw = generate_response(goal, provider=self.provider, system_prompt=_PLAN_SYSTEM)
        plan = self._parse_plan(raw, goal)
        self._last_plan = plan
        return plan

    def get_last_plan(self) -> Optional[Dict[str, Any]]:
        """Return the most recently created plan."""
        return self._last_plan

    def _guess_tool(self, task_description: str) -> str:
        """Heuristically determine the best tool for a task description."""
        lower = task_description.lower()
        if any(k in lower for k in _TERMINAL_KEYWORDS):
            return "terminal"
        if any(k in lower for k in _BROWSER_KEYWORDS):
            return "browser"
        if any(k in lower for k in _FILE_KEYWORDS):
            return "file_io"
        return "llm"

    # ── Parsing Helpers ───────────────────────────────────────────────────────

    def _parse_plan(self, raw: str, goal: str) -> Dict[str, Any]:
        """Try JSON first; fall back to numbered-list parsing."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw.strip(), flags=re.DOTALL).strip()

        # Try direct JSON parse
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and "steps" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to find a JSON object embedded in text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, dict) and "steps" in data:
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: parse as numbered list
        return self._parse_numbered_list(raw, goal)

    def _parse_numbered_list(self, text: str, goal: str) -> Dict[str, Any]:
        """Convert a '1. Do X\n2. Do Y' style response into a plan dict."""
        steps = []
        for line in text.strip().splitlines():
            # Match lines like "1. Do something" or "- Do something"
            m = re.match(r"^[\d\-\*]+[.)\s]+(.+)$", line.strip())
            if m:
                task_text = m.group(1).strip()
                # Capitalise first letter
                task_text = task_text[0].upper() + task_text[1:] if task_text else task_text
                step_id = len(steps) + 1
                steps.append({
                    "id": step_id,
                    "task": task_text,
                    "tools": [self._guess_tool(task_text)],
                    "depends_on": [step_id - 1] if step_id > 1 else [],
                    "expected_output": "completed",
                })

        return {
            "goal": goal,
            "steps": steps,
            "estimated_time": "unknown",
            "tools_required": list({t for s in steps for t in s.get("tools", [])}),
        }
