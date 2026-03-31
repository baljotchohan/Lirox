"""
Lirox v0.3 — Structured Task Planner

Converts user goals into structured, executable plans with:
- Step-by-step breakdown with tool requirements
- Dependency tracking between steps
- Time estimates
- Robust JSON parsing with fallback to flat list
"""

import json
import re
from lirox.utils.llm import generate_response
from lirox.utils.errors import PlanValidationError


# The LLM prompt template for plan generation
PLAN_PROMPT = """You are a task planning expert. Break this goal into concrete, executable steps.

Goal: {goal}

Available tools:
- "terminal" — run shell commands (mkdir, pip, python, npm, git, etc.)
- "browser"  — fetch web pages, search the internet, extract data
- "file_io"  — read/write/list files safely
- "llm"      — reasoning, analysis, writing, summarization (default)

Create a detailed plan as JSON with this EXACT structure:
{{
  "goal": "user's goal",
  "steps": [
    {{
      "id": 1,
      "task": "clear description of what to do",
      "tools": ["llm"],
      "depends_on": [],
      "expected_output": "what success looks like"
    }}
  ],
  "estimated_time": "X minutes",
  "tools_required": ["llm"]
}}

Rules:
- Each step must have a single, concrete action
- Use the correct tool for each step
- Set depends_on to list IDs of steps that must complete first
- Keep steps to 3-7 for most tasks
- Return ONLY valid JSON. No explanation, no markdown fences.
"""


class Planner:
    """Converts user goals into structured, executable plans."""

    def __init__(self, provider="auto"):
        self.provider = provider
        self.last_plan = None  # Store last plan for /execute-plan command

    def set_provider(self, provider):
        self.provider = provider

    def create_plan(self, goal, system_prompt=None, context=None):
        """
        Convert a goal into a structured plan dict.

        Args:
            goal: User's goal string
            system_prompt: System prompt for LLM context
            context: Optional reasoning trace to append to the prompt

        Returns:
            Plan dict with structured steps, or fallback plan on parse failure
        """
        prompt = PLAN_PROMPT.format(goal=goal)
        if context:
            prompt += f"\n\nContext / reasoning trace:\n{context[:2000]}"

        response = generate_response(prompt, self.provider, system_prompt=system_prompt)
        plan = self._parse_plan_response(response, goal)

        # Validate and store
        plan = self._validate_plan(plan)
        self.last_plan = plan
        return plan

    def _parse_plan_response(self, response, goal):
        """
        Robustly extract plan JSON from LLM response.
        Handles markdown fences, extra text, and malformed JSON.
        Falls back to flat list parsing if JSON fails.
        """
        # Attempt 1: Direct JSON parse
        try:
            plan = json.loads(response.strip())
            if isinstance(plan, dict) and "steps" in plan:
                return plan
        except (json.JSONDecodeError, ValueError):
            pass

        # Attempt 2: Extract JSON from markdown code fences
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        if json_match:
            try:
                plan = json.loads(json_match.group(1).strip())
                if isinstance(plan, dict) and "steps" in plan:
                    return plan
            except (json.JSONDecodeError, ValueError):
                pass

        # Attempt 3: Find JSON object in response text
        brace_match = re.search(r'\{.*\}', response, re.DOTALL)
        if brace_match:
            try:
                plan = json.loads(brace_match.group(0))
                if isinstance(plan, dict) and "steps" in plan:
                    return plan
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: Parse as flat numbered list (v0.2 style) and wrap in plan dict
        return self._fallback_flat_plan(response, goal)

    def _fallback_flat_plan(self, response, goal):
        """
        Parse a flat numbered list response and wrap in structured plan dict.
        This is the v0.2 fallback when the LLM can't produce valid JSON.
        """
        steps = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove leading numbers/dots/dashes
                item = line.lstrip('0123456789.- ')
                if item:
                    steps.append(item)

        if not steps:
            # Absolute fallback: treat entire response as a single step
            steps = [response.strip()[:200]]

        # Wrap in plan dict
        plan_steps = []
        for i, step_text in enumerate(steps, 1):
            tool = self._guess_tool(step_text)
            plan_steps.append({
                "id": i,
                "task": step_text,
                "tools": [tool],
                "depends_on": [i - 1] if i > 1 else [],
                "expected_output": "Step completed successfully"
            })

        return {
            "goal": goal,
            "steps": plan_steps,
            "estimated_time": f"{len(plan_steps) * 2} minutes",
            "tools_required": list(set(s["tools"][0] for s in plan_steps))
        }

    def _guess_tool(self, step_text):
        """Heuristic to guess which tool a step needs based on keywords."""
        lowered = step_text.lower()

        terminal_keywords = [
            "run", "install", "create directory", "mkdir", "pip", "npm",
            "execute", "command", "terminal", "shell", "cd", "git"
        ]
        browser_keywords = [
            "search", "browse", "fetch", "web", "url", "http",
            "scrape", "download page", "lookup", "research online"
        ]
        file_keywords = [
            "write file", "save to", "read file", "create file",
            "output to", "save as", "write to"
        ]

        if any(k in lowered for k in terminal_keywords):
            return "terminal"
        if any(k in lowered for k in browser_keywords):
            return "browser"
        if any(k in lowered for k in file_keywords):
            return "file_io"
        return "llm"

    def _validate_plan(self, plan):
        """
        Validate plan structure and fill in missing fields with defaults.
        Ensures every step has required fields.
        """
        if not isinstance(plan, dict):
            raise PlanValidationError("Plan must be a dictionary")

        if "steps" not in plan or not plan["steps"]:
            raise PlanValidationError("Plan must have at least one step")

        # Ensure top-level fields
        plan.setdefault("goal", "Unknown goal")
        plan.setdefault("estimated_time", "Unknown")
        plan.setdefault("tools_required", [])

        # Validate each step
        valid_steps = []
        for i, step in enumerate(plan["steps"]):
            if not isinstance(step, dict):
                # Convert string steps to proper dicts
                step = {
                    "id": i + 1,
                    "task": str(step),
                    "tools": ["llm"],
                    "depends_on": [i] if i > 0 else [],
                    "expected_output": "Step completed"
                }

            step.setdefault("id", i + 1)
            step.setdefault("task", f"Step {i + 1}")
            step.setdefault("tools", ["llm"])
            step.setdefault("depends_on", [])
            step.setdefault("expected_output", "Step completed")

            # Ensure tools is a list
            if isinstance(step["tools"], str):
                step["tools"] = [step["tools"]]

            valid_steps.append(step)

        plan["steps"] = valid_steps

        # Rebuild tools_required from steps
        all_tools = set()
        for step in plan["steps"]:
            all_tools.update(step["tools"])
        plan["tools_required"] = list(all_tools)

        return plan

    def get_last_plan(self):
        """Return the last generated plan (for /execute-plan command)."""
        return self.last_plan
