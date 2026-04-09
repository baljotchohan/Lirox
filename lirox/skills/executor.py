"""
Lirox v1.0.0 — Skill Executor
Runs a saved skill inside the agent context, injecting its parameters
into an LLM prompt and returning the result.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from lirox.skills.manager import SkillManager
from lirox.utils.llm import generate_response


class SkillExecutor:
    """
    Executes a named skill with the given parameter values.

    Usage::

        executor = SkillExecutor()
        result   = executor.run("summarise_text", {"text": "Hello world"})
    """

    def __init__(self, manager: Optional[SkillManager] = None) -> None:
        self.manager = manager or SkillManager()

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, skill_name: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute the skill identified by *skill_name*.

        Parameters
        ----------
        skill_name:
            The skill's name as stored on disk (case-insensitive).
        params:
            A dictionary of parameter values to substitute into the skill
            prompt.  If *None*, an empty dict is used.

        Returns
        -------
        str
            The LLM-generated result, or an error message if execution fails.
        """
        params = params or {}
        skill  = self.manager.get_skill(skill_name)

        if skill is None:
            available = ", ".join(
                s["name"] for s in self.manager.list_skills()
            ) or "none"
            return (
                f"❌ Skill '{skill_name}' not found.\n"
                f"Available skills: {available}\n"
                f"Create one with: /add-skill <description>"
            )

        prompt = self._build_prompt(skill, params)
        try:
            result = generate_response(
                prompt,
                provider="auto",
                system_prompt=(
                    f"You are executing the '{skill['name']}' skill. "
                    f"{skill.get('description', '')} "
                    f"Follow the implementation instructions exactly."
                ),
            )
            return f"✅ Skill '{skill['name']}' result:\n\n{result}"
        except Exception as e:
            return f"❌ Skill execution error: {e}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_prompt(
        self, skill: Dict[str, Any], params: Dict[str, Any]
    ) -> str:
        """Build the execution prompt from skill definition and user params."""
        lines = [
            f"SKILL: {skill.get('name', 'unknown')}",
            f"DESCRIPTION: {skill.get('description', '')}",
            f"IMPLEMENTATION: {skill.get('implementation', 'Execute the skill as described.')}",
            "",
            "PARAMETERS:",
        ]
        for param_def in skill.get("parameters", []):
            pname = param_def.get("name", "")
            ptype = param_def.get("type", "string")
            value = params.get(pname, param_def.get("default", ""))
            lines.append(f"  {pname} ({ptype}): {value}")

        lines += [
            "",
            "Execute the skill with the parameters above and return the result.",
        ]
        return "\n".join(lines)
