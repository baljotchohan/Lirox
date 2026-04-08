"""
Lirox v2.0 — Planner

Converts a high-level goal into a structured multi-step execution plan.
Uses LLM to generate JSON plans, with fallback parsing for plain-text lists.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Dict, Any, List

from lirox.utils.llm import generate_response


PLAN_PROMPT = """Create a detailed execution plan for the following goal.

Goal: {goal}

Return ONLY valid JSON in this exact format:
{{
  "goal": "{goal}",
  "steps": [
    {{
      "id": 1,
      "task": "Description of step",
      "tools": ["tool_name"],
      "depends_on": [],
      "expected_output": "What this step produces"
    }}
  ],
  "estimated_time": "X minutes",
  "tools_required": ["tool1", "tool2"]
}}

Each step must have id, task, tools (list), depends_on (list of step ids), expected_output.
"""

_TERMINAL_KEYWORDS = ["install", "run", "execute", "terminal", "command", "bash", "shell", "script", "pip", "npm", "build", "compile"]
_BROWSER_KEYWORDS  = ["search", "browse", "fetch", "url", "web", "website", "http", "scrape", "google", "bing", "internet"]
_FILE_KEYWORDS     = ["write file", "read file", "save", "save to", "load file", "open file", "create file", "disk", "file_io", "write to"]


class Planner:
    """Converts goals into structured, multi-step execution plans."""

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self._last_plan: Optional[Dict[str, Any]] = None

    def create_plan(self, goal: str) -> Dict[str, Any]:
        """
        Generate a structured plan for the given goal.

        Returns a dict with at minimum:
          - goal: str
          - steps: list of {id, task, tools, depends_on, expected_output}
          - estimated_time: str
          - tools_required: list
        """
        prompt = PLAN_PROMPT.format(goal=goal)
        raw = generate_response(prompt, provider=self.provider)

        plan = self._parse_plan(raw, goal)
        self._last_plan = plan
        return plan

    def get_last_plan(self) -> Optional[Dict[str, Any]]:
        """Return the most recently created plan."""
        return self._last_plan

    def _parse_plan(self, raw: str, goal: str) -> Dict[str, Any]:
        """Parse LLM output into a plan dict. Falls back to flat-list parsing."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # Try JSON parse
        try:
            plan = json.loads(cleaned)
            if isinstance(plan, dict) and "steps" in plan:
                # Normalize each step
                normalized = []
                for i, step in enumerate(plan["steps"]):
                    normalized.append({
                        "id":              step.get("id", i + 1),
                        "task":            step.get("task", step.get("description", "")),
                        "tools":           step.get("tools", [self._guess_tool(step.get("task", ""))]),
                        "depends_on":      step.get("depends_on", []),
                        "expected_output": step.get("expected_output", ""),
                    })
                plan["steps"] = normalized
                if "goal" not in plan:
                    plan["goal"] = goal
                return plan
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: parse numbered list
        return self._parse_numbered_list(raw, goal)

    def _parse_numbered_list(self, text: str, goal: str) -> Dict[str, Any]:
        """Parse plain-text numbered list into plan steps."""
        steps = []
        # Match lines like "1. Do something" or "1) Do something"
        pattern = re.compile(r"^\s*\d+[\.\)]\s+(.+)$", re.MULTILINE)
        matches = pattern.findall(text)

        for i, task_text in enumerate(matches):
            task_text = task_text.strip()
            steps.append({
                "id":              i + 1,
                "task":            task_text,
                "tools":           [self._guess_tool(task_text)],
                "depends_on":      [i] if i > 0 else [],
                "expected_output": "",
            })

        if not steps:
            # Last resort: treat every non-empty line as a step
            for i, line in enumerate(text.splitlines()):
                line = line.strip(" -•*\t")
                if line:
                    steps.append({
                        "id":              i + 1,
                        "task":            line,
                        "tools":           [self._guess_tool(line)],
                        "depends_on":      [],
                        "expected_output": "",
                    })

        return {
            "goal":           goal,
            "steps":          steps,
            "estimated_time": "unknown",
            "tools_required": list({t for s in steps for t in s["tools"]}),
        }

    def _guess_tool(self, task_text: str) -> str:
        """Heuristically guess the best tool for a task description."""
        text_lower = task_text.lower()

        for kw in _FILE_KEYWORDS:
            if kw in text_lower:
                return "file_io"

        for kw in _TERMINAL_KEYWORDS:
            if kw in text_lower:
                return "terminal"

        for kw in _BROWSER_KEYWORDS:
            if kw in text_lower:
                return "browser"

        return "llm"
