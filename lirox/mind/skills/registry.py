"""
Lirox v0.5 — Skills Registry

Skills are Python modules that give the Mind Agent new capabilities.
They live in data/mind/skills/ and are dynamically loaded at startup.

A skill must expose:
  SKILL_NAME: str
  SKILL_DESCRIPTION: str
  def run(query: str, context: dict) -> str:
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from lirox.config import MIND_SKILLS_DIR
from lirox.utils.llm import generate_response


# ── Skill builder prompt ──────────────────────────────────────────────────────

_BUILD_SKILL_PROMPT = """
You are writing a Python skill module for a personal AI agent called Lirox.

USER REQUEST: {description}

Write a complete Python module that:
1. Has SKILL_NAME = "short_name" (snake_case, no spaces)
2. Has SKILL_DESCRIPTION = "One line description"
3. Has a `run(query: str, context: dict) -> str` function
4. The run() function does what the user wants and returns a string result
5. Handles all errors with try/except
6. Is self-contained (imports only stdlib or common packages)

RULES:
- No class definitions needed, just module-level code + run()
- Keep it focused on ONE thing
- Add basic docstring to run()
- Never do anything destructive (no file deletion, no system calls without good reason)

Output ONLY the Python code, no markdown fences, no explanation.
"""

_FIX_SKILL_PROMPT = """
This Python skill module has an error:

ERROR:
{error}

CURRENT CODE:
{code}

Fix the error and output ONLY the corrected Python code (no markdown, no explanation).
"""


class SkillsRegistry:
    """
    Manages the collection of user-defined skills for the Mind Agent.
    """

    def __init__(self):
        self._dir = Path(MIND_SKILLS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, Any] = {}  # name → module
        self._meta: Dict[str, Dict] = {}   # name → {description, path, loaded_at}
        self._load_all()

    def _load_all(self) -> None:
        """Load all .py skill files from the skills directory."""
        for path in self._dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            try:
                self._load_skill_file(path)
            except Exception as e:
                print(f"  [skill] Failed to load {path.name}: {e}")

    def _load_skill_file(self, path: Path) -> Optional[str]:
        """
        Dynamically load a skill module.
        Returns skill name on success, None on failure.
        """
        spec = importlib.util.spec_from_file_location(
            f"lirox_skill_{path.stem}", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        name = getattr(mod, "SKILL_NAME", path.stem)
        desc = getattr(mod, "SKILL_DESCRIPTION", "No description")

        if not hasattr(mod, "run"):
            raise ValueError(f"Skill {path.name} has no run() function")

        self._skills[name] = mod
        self._meta[name] = {
            "description": desc,
            "path": str(path),
            "loaded_at": time.time(),
        }
        return name

    def list_skills(self) -> List[Dict]:
        """Return list of loaded skills with metadata."""
        return [
            {"name": name, **meta}
            for name, meta in self._meta.items()
        ]

    def run_skill(self, name: str, query: str, context: dict = None) -> str:
        """Execute a skill by name."""
        if name not in self._skills:
            # Try fuzzy match
            matches = [n for n in self._skills if query.lower() in n.lower()]
            if matches:
                name = matches[0]
            else:
                return f"Skill '{name}' not found. Available: {', '.join(self._skills.keys())}"

        try:
            result = self._skills[name].run(query, context or {})
            return str(result) if result is not None else "Skill returned no output."
        except Exception as e:
            return f"Skill '{name}' error: {e}"

    def find_relevant_skill(self, query: str) -> Optional[str]:
        """
        Find the most relevant skill for a query.
        BUG-6 FIX: requires 2+ matching meaningful words to avoid false positives.
        """
        if not self._skills:
            return None

        # Common words that should not trigger a skill match alone
        _STOP = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'can', 'this', 'that', 'with', 'from',
            'for', 'and', 'but', 'or', 'not', 'all', 'any', 'some', 'more',
            'what', 'when', 'where', 'who', 'how', 'why', 'your', 'my', 'our',
            'text', 'file', 'data', 'help', 'make', 'use', 'get', 'run', 'show',
            'list', 'find', 'give', 'tell', 'want', 'need', 'like', 'just',
        }

        query_lower = query.lower()
        query_words = {w for w in query_lower.split() if len(w) > 3 and w not in _STOP}

        best_name  = None
        best_score = 0

        for name, meta in self._meta.items():
            desc_words = {w for w in meta["description"].lower().split()
                          if len(w) > 3 and w not in _STOP}
            matches    = query_words & desc_words
            score      = len(matches)

            # Require at least 2 meaningful word matches to activate a skill
            if score >= 2 and score > best_score:
                best_score = score
                best_name  = name

        return best_name

    # ── Build new skill ───────────────────────────────────────────────────────

    def build_skill_from_description(self, description: str) -> Dict[str, Any]:
        """
        Use LLM to write a skill from a plain English description.
        Returns {success, name, path, error}
        """
        try:
            code = generate_response(
                _BUILD_SKILL_PROMPT.format(description=description),
                provider="auto",
                system_prompt="You write Python skill modules. Output ONLY Python code.",
            )

            # Clean up code
            code = code.strip()
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            code = code.strip()

            # Test compile
            try:
                compile(code, "<skill>", "exec")
            except SyntaxError as se:
                # Try to auto-fix
                fixed = generate_response(
                    _FIX_SKILL_PROMPT.format(error=str(se), code=code),
                    provider="auto",
                    system_prompt="Fix Python syntax. Output ONLY code.",
                )
                from lirox.utils.llm import strip_code_fences
                fixed = strip_code_fences(fixed, lang="python")
                compile(fixed, "<skill>", "exec")
                code = fixed

            # Extract skill name from code
            import re
            m = re.search(r'SKILL_NAME\s*=\s*["\']([^"\']+)["\']', code)
            skill_name = m.group(1) if m else "custom_skill_" + str(int(time.time()))[-4:]

            # Save skill file
            skill_path = self._dir / f"{skill_name}.py"
            skill_path.write_text(code)

            # Load it
            loaded_name = self._load_skill_file(skill_path)

            return {
                "success": True,
                "name": loaded_name or skill_name,
                "path": str(skill_path),
                "code": code,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_skill_from_code(self, code: str, name: str = None) -> Dict[str, Any]:
        """
        Add a skill from raw Python code provided by the user.
        """
        import re
        try:
            code = code.strip()
            # Clean markdown fences
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            code = code.strip()

            compile(code, "<skill>", "exec")

            m = re.search(r'SKILL_NAME\s*=\s*["\']([^"\']+)["\']', code)
            skill_name = name or (m.group(1) if m else "custom_" + str(int(time.time()))[-4:])
            skill_name = re.sub(r"[^a-z0-9_]", "_", skill_name.lower())

            # Inject SKILL_NAME if missing
            if "SKILL_NAME" not in code:
                code = f'SKILL_NAME = "{skill_name}"\nSKILL_DESCRIPTION = "User-provided skill"\n\n' + code

            skill_path = self._dir / f"{skill_name}.py"
            skill_path.write_text(code)
            loaded = self._load_skill_file(skill_path)

            return {"success": True, "name": loaded or skill_name, "path": str(skill_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_skill(self, name: str) -> bool:
        """Remove a skill."""
        if name in self._meta:
            path = Path(self._meta[name]["path"])
            if path.exists():
                path.unlink()
            self._skills.pop(name, None)
            self._meta.pop(name, None)
            return True
        return False
