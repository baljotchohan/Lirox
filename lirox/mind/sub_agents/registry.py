"""Lirox v1.1 — Sub-Agents Registry.

Hardened over v0.5:
  - AST-based contract enforcement.
  - Stricter detection: only @name, `hey name,`, or `ask name to` —
    the greedy "name: anything" pattern was removed because it
    routed normal sentences like "python: an interpreted language"
    to a registered sub-agent named python.
  - Enriched context (niche, current_project, etc.) passed to agents.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lirox.config import MIND_AGENTS_DIR


def _has_valid_run(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            args = [a.arg for a in node.args.args]
            return len(args) >= 2 and args[0] == "query" and args[1] == "context"
    return False


class SubAgentsRegistry:
    """Named sub-agents for the Mind Agent."""

    def __init__(self):
        self._dir = Path(MIND_AGENTS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, Any] = {}
        self._meta: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        from lirox.utils.structured_logger import get_logger
        log = get_logger("lirox.sub_agents")
        for path in self._dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            try:
                self._load_agent_file(path)
            except Exception as e:
                log.warning(f"Failed to load sub-agent {path.name}: {e}")

    def _load_agent_file(self, path: Path) -> Optional[str]:
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ValueError(f"Cannot read agent file: {e}")
        if not _has_valid_run(src):
            raise ValueError(
                f"{path.name}: missing `def run(query, context)` (contract violation)."
            )

        spec = importlib.util.spec_from_file_location(
            f"lirox_agent_{path.stem}", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        name = getattr(mod, "AGENT_NAME", path.stem).lower()
        desc = getattr(mod, "AGENT_DESCRIPTION", "No description")

        if not hasattr(mod, "run"):
            raise ValueError(f"{path.name}: no run() function")

        self._agents[name] = mod
        self._meta[name] = {
            "description": desc,
            "path":        str(path),
            "loaded_at":   time.time(),
        }
        return name

    def list_agents(self) -> List[Dict]:
        return [{"name": n, **m} for n, m in self._meta.items()]

    def detect_agent_call(self, query: str) -> Optional[Tuple[str, str]]:
        """Explicit detection only. Returns (name, cleaned_query) or None.

        Recognised forms (in order):
          * @name <query>
          * hey <name>, <query>
          * ask <name> to <query>

        The bare `<name>: <query>` pattern was removed because it
        produced false positives on normal sentences like
        "python: an interpreted language".
        """
        q = query.strip()

        m = re.match(r"@(\w+)\s+(.+)", q)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        m = re.match(r"hey\s+(\w+)[,\s]+(.+)", q, re.IGNORECASE)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        m = re.match(r"ask\s+(\w+)\s+to\s+(.+)", q, re.IGNORECASE)
        if m:
            name = m.group(1).lower()
            if name in self._agents:
                return name, m.group(2).strip()

        return None

    def _enriched_context(self, user_context: Optional[dict]) -> dict:
        ctx = dict(user_context or {})
        try:
            from lirox.agent.profile import UserProfile
            prof = UserProfile().data
            ctx.setdefault("niche", prof.get("niche", ""))
            ctx.setdefault("current_project", prof.get("current_project", ""))
            ctx.setdefault("user_name", prof.get("user_name", ""))
            ctx.setdefault("preferences", prof.get("preferences", {}))
        except Exception:
            pass
        try:
            from lirox.mind.agent import get_learnings
            if "user_profile" not in ctx:
                ctx["user_profile"] = get_learnings().to_context_string()
        except Exception:
            pass
        return ctx

    def run_agent(self, name: str, query: str,
                  context: Optional[dict] = None) -> str:
        name = name.lower()
        if name not in self._agents:
            return (f"Sub-agent '{name}' not found. "
                    f"Available: {', '.join(self._agents.keys()) or 'none'}")
        try:
            enriched = self._enriched_context(context)
            result = self._agents[name].run(query, enriched)
            return str(result) if result is not None else f"Agent '{name}' returned no output."
        except TypeError as e:
            return (f"Sub-agent '{name}' has wrong signature. "
                    f"Expected run(query, context). Error: {e}")
        except Exception as e:
            return f"Sub-agent '{name}' error: {e}"

    def add_agent_from_code(self, code: str, name: str) -> Dict[str, Any]:
        try:
            code = code.strip()
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            code = code.strip()

            safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())

            if "AGENT_NAME" not in code:
                code = (
                    f'AGENT_NAME = "{safe_name}"\n'
                    f'AGENT_DESCRIPTION = "Custom sub-agent: {name}"\n\n'
                ) + code

            compile(code, "<agent>", "exec")
            if not _has_valid_run(code):
                return {"success": False,
                        "error": "Module must define `def run(query, context)`."}

            agent_path = self._dir / f"{safe_name}.py"
            agent_path.write_text(code, encoding="utf-8")

            self._agents.pop(safe_name, None)
            self._meta.pop(safe_name, None)

            loaded = self._load_agent_file(agent_path)
            return {"success": True, "name": loaded or safe_name,
                    "path": str(agent_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def build_agent_from_description_stream(self, description: str,
                                            name: str = "CustomAgent"):
        from lirox.agents.agent_builder import AgentBuilder
        yield from AgentBuilder().build_agent_stream(
            description, name=name, registry=self
        )

    def build_agent_from_description(self, description: str, name: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"success": False}
        for event in self.build_agent_from_description_stream(description, name=name):
            if event.get("type") == "done":
                return event.get("result", result)
        return result

    def remove_agent(self, name: str) -> bool:
        name = name.lower()
        if name in self._meta:
            Path(self._meta[name]["path"]).unlink(missing_ok=True)
            self._agents.pop(name, None)
            self._meta.pop(name, None)
            return True
        return False
