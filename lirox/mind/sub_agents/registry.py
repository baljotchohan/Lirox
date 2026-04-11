"""
Lirox v0.5 — Sub-Agents Registry

Sub-agents are specialized agents the user adds to extend the Mind Agent.
Each sub-agent has a name and can be called by name in queries.

Example: "hey max, find me the top GitHub repos today"
  → routes to sub-agent named 'max'

A sub-agent module must expose:
  AGENT_NAME: str
  AGENT_DESCRIPTION: str
  def run(query: str, context: dict) -> str
"""
from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from lirox.config import MIND_AGENTS_DIR
from lirox.utils.llm import generate_response


_BUILD_AGENT_PROMPT = """
You are writing a Python sub-agent module for Lirox.

AGENT PURPOSE: {description}
AGENT NAME: {name}

Write a complete Python module:
1. AGENT_NAME = "{name}"
2. AGENT_DESCRIPTION = "One line description of what this agent does"
3. def run(query: str, context: dict) -> str:
   - Does what the agent is supposed to do
   - Returns a string response
   - Handles all errors with try/except
   - Can use requests, stdlib, os (but NOT lirox internals)

Keep it focused and self-contained.
Output ONLY Python code, no markdown, no explanation.
"""


class SubAgentsRegistry:
    """Manages named sub-agents for the Mind Agent."""

    def __init__(self):
        self._dir = Path(MIND_AGENTS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, Any] = {}
        self._meta: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self):
        from lirox.utils.structured_logger import get_logger
        _log = get_logger("lirox.sub_agents")
        for path in self._dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            try:
                self._load_agent_file(path)
            except Exception as e:
                _log.warning(f"Failed to load sub-agent {path.name}: {e}")

    def _load_agent_file(self, path: Path) -> Optional[str]:
        spec = importlib.util.spec_from_file_location(
            f"lirox_agent_{path.stem}", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        name = getattr(mod, "AGENT_NAME", path.stem).lower()
        desc = getattr(mod, "AGENT_DESCRIPTION", "No description")

        if not hasattr(mod, "run"):
            raise ValueError(f"Sub-agent {path.name} has no run() function")

        self._agents[name] = mod
        self._meta[name] = {
            "description": desc,
            "path": str(path),
            "loaded_at": time.time(),
        }
        return name

    def list_agents(self) -> List[Dict]:
        return [{"name": n, **m} for n, m in self._meta.items()]

    def detect_agent_call(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Detect if query is calling a named sub-agent.
        Patterns: "hey max, ...", "@max ...", "max: ...", "ask max to ..."
        Returns (agent_name, cleaned_query) or None.
        """
        q = query.strip()

        # Pattern: "hey <name>, ..." or "hey <name> ..."
        m = re.match(r"(?:hey\s+)(\w+)[,\s]+(.+)", q, re.IGNORECASE)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        # Pattern: "@<name> ..."
        m = re.match(r"@(\w+)\s+(.+)", q)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        # Pattern: "<name>: ..."
        m = re.match(r"(\w+):\s+(.+)", q)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        # Pattern: "ask <name> to ..."
        m = re.match(r"ask\s+(\w+)\s+to\s+(.+)", q, re.IGNORECASE)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        return None

    def run_agent(self, name: str, query: str, context: dict = None) -> str:
        """Execute a sub-agent by name."""
        if name not in self._agents:
            return f"Sub-agent '{name}' not found. Available: {', '.join(self._agents.keys())}"
        try:
            result = self._agents[name].run(query, context or {})
            return str(result) if result is not None else f"Agent '{name}' returned no output."
        except Exception as e:
            return f"Sub-agent '{name}' error: {e}"

    def add_agent_from_code(self, code: str, name: str) -> Dict[str, Any]:
        """Add a sub-agent from raw code."""
        try:
            code = code.strip()
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            code = code.strip()

            safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())

            # Inject AGENT_NAME if missing
            if "AGENT_NAME" not in code:
                code = f'AGENT_NAME = "{safe_name}"\nAGENT_DESCRIPTION = "Custom sub-agent: {name}"\n\n' + code

            compile(code, "<agent>", "exec")

            agent_path = self._dir / f"{safe_name}.py"
            agent_path.write_text(code)
            loaded = self._load_agent_file(agent_path)

            return {"success": True, "name": loaded or safe_name, "path": str(agent_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def build_agent_from_description(self, description: str, name: str) -> Dict[str, Any]:
        """Build a sub-agent from a plain English description using LLM."""
        try:
            code = generate_response(
                _BUILD_AGENT_PROMPT.format(description=description, name=name),
                provider="auto",
                system_prompt="Write Python agent module. Output ONLY code.",
            )
            return self.add_agent_from_code(code, name)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_agent(self, name: str) -> bool:
        name = name.lower()
        if name in self._meta:
            Path(self._meta[name]["path"]).unlink(missing_ok=True)
            self._agents.pop(name, None)
            self._meta.pop(name, None)
            return True
        return False
