"""Lirox v1.1 — Skills Registry.

Hardened over v0.5:
  - AST-based contract enforcement: a skill must define
    `def run(query, context)` or it is rejected at load time.
  - run_skill() injects structured profile data (niche, current_project,
    preferences) into context, not just a flat string.
  - find_relevant_skill() requires >=2 meaningful word matches and uses
    a recency tiebreaker so newer skills win on equal score.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.config import MIND_SKILLS_DIR


_STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'this', 'that', 'with', 'from',
    'for', 'and', 'but', 'or', 'not', 'all', 'any', 'some', 'more',
    'what', 'when', 'where', 'who', 'how', 'why', 'your', 'my', 'our',
    'text', 'file', 'data', 'help', 'make', 'use', 'get', 'run', 'show',
    'list', 'find', 'give', 'tell', 'want', 'need', 'like', 'just',
}


def _has_valid_run(code: str) -> bool:
    """AST check: module defines `def run(query, context, ...)`."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            args = [a.arg for a in node.args.args]
            return len(args) >= 2 and args[0] == "query" and args[1] == "context"
    return False


class SkillsRegistry:
    """User-defined skills for the Mind Agent."""

    def __init__(self):
        self._dir = Path(MIND_SKILLS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, Any] = {}
        self._meta: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        from lirox.utils.structured_logger import get_logger
        log = get_logger("lirox.skills")
        for path in self._dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            try:
                self._load_skill_file(path)
            except Exception as e:
                log.warning(f"Failed to load skill {path.name}: {e}")

    def _load_skill_file(self, path: Path) -> Optional[str]:
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ValueError(f"Cannot read skill file: {e}")
        if not _has_valid_run(src):
            raise ValueError(
                f"{path.name}: missing `def run(query, context)` (contract violation)."
            )

        spec = importlib.util.spec_from_file_location(
            f"lirox_skill_{path.stem}", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        name = getattr(mod, "SKILL_NAME", path.stem)
        desc = getattr(mod, "SKILL_DESCRIPTION", "No description")

        if not hasattr(mod, "run"):
            raise ValueError(f"{path.name}: has no run() function")

        self._skills[name] = mod
        self._meta[name] = {
            "description": desc,
            "path":        str(path),
            "loaded_at":   time.time(),
        }
        return name

    def list_skills(self) -> List[Dict]:
        return [{"name": name, **meta} for name, meta in self._meta.items()]

    def _enriched_context(self, user_context: Optional[dict]) -> dict:
        """Add structured profile data to skill context."""
        ctx = dict(user_context or {})
        try:
            from lirox.agent.profile import UserProfile
            prof = UserProfile().data
            ctx.setdefault("niche", prof.get("niche", ""))
            ctx.setdefault("current_project", prof.get("current_project", ""))
            ctx.setdefault("user_name", prof.get("user_name", ""))
            ctx.setdefault("profession", prof.get("profession", ""))
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

    def run_skill(self, name: str, query: str,
                  context: Optional[dict] = None) -> str:
        if name not in self._skills:
            matches = [n for n in self._skills if query.lower() in n.lower()]
            if matches:
                name = matches[0]
            else:
                return (f"Skill '{name}' not found. "
                        f"Available: {', '.join(self._skills.keys()) or 'none'}")
        try:
            enriched = self._enriched_context(context)
            result = self._skills[name].run(query, enriched)
            return str(result) if result is not None else "Skill returned no output."
        except TypeError as e:
            return (f"Skill '{name}' has wrong signature. Expected "
                    f"run(query, context). Error: {e}")
        except Exception as e:
            return f"Skill '{name}' error: {e}"

    def find_relevant_skill(self, query: str) -> Optional[str]:
        if not self._skills:
            return None
        qwords = {w for w in re.findall(r"\b\w{4,}\b", query.lower())
                  if w not in _STOP_WORDS}
        if len(qwords) < 2:
            return None

        best_name: Optional[str] = None
        best_score = 0.0
        now = time.time()
        for name, meta in self._meta.items():
            desc = (meta.get("description") or "").lower()
            dwords = {w for w in re.findall(r"\b\w{4,}\b", desc)
                      if w not in _STOP_WORDS}
            score = len(qwords & dwords)
            if score < 2:
                continue
            # Newer skills get a tiny boost on equal scores
            age_days = max(0.0, (now - meta.get("loaded_at", now)) / 86400.0)
            adjusted = score - 0.01 * min(age_days, 30)
            if adjusted > best_score:
                best_score = adjusted
                best_name = name
        return best_name

    # ── Build (defers to AgentBuilder) ────────────────────────

    def build_skill_from_description_stream(self, description: str):
        from lirox.agents.agent_builder import AgentBuilder
        yield from AgentBuilder().build_skill_stream(description, registry=self)

    def build_skill_from_description(self, description: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"success": False}
        for event in self.build_skill_from_description_stream(description):
            if event.get("type") == "done":
                return event.get("result", result)
        return result

    def add_skill_from_code(self, code: str, name: str = None) -> Dict[str, Any]:
        try:
            code = code.strip()
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            code = code.strip()

            compile(code, "<skill>", "exec")

            if not _has_valid_run(code):
                return {"success": False,
                        "error": "Module must define `def run(query, context)`."}

            m = re.search(r'SKILL_NAME\s*=\s*["\']([^"\']+)["\']', code)
            skill_name = name or (m.group(1) if m else f"custom_{int(time.time()) % 10000}")
            skill_name = re.sub(r"[^a-z0-9_]", "_", skill_name.lower())

            if "SKILL_NAME" not in code:
                code = (
                    f'SKILL_NAME = "{skill_name}"\n'
                    f'SKILL_DESCRIPTION = "User-provided skill"\n\n'
                ) + code

            skill_path = self._dir / f"{skill_name}.py"
            skill_path.write_text(code, encoding="utf-8")

            self._skills.pop(skill_name, None)
            self._meta.pop(skill_name, None)

            loaded = self._load_skill_file(skill_path)
            return {"success": True, "name": loaded or skill_name,
                    "path": str(skill_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_skill(self, name: str) -> bool:
        if name in self._meta:
            path = Path(self._meta[name]["path"])
            if path.exists():
                path.unlink()
            self._skills.pop(name, None)
            self._meta.pop(name, None)
            return True
        return False
