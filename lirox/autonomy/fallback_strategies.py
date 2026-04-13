"""Lirox Autonomy — Fallback Strategies.

When the agent cannot execute its primary plan (e.g. permission denied),
this module generates and ranks alternative approaches with trade-off
descriptions so the user can make an informed choice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from lirox.autonomy.permission_system import PermissionTier


@dataclass
class Alternative:
    """A lower-permission workaround for a denied action."""
    title:       str
    description: str
    pros:        List[str] = field(default_factory=list)
    cons:        List[str] = field(default_factory=list)
    min_tier:    PermissionTier = PermissionTier.BASIC


@dataclass
class FallbackPlan:
    original_action: str
    denied_tier:     PermissionTier
    alternatives:    List[Alternative] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Original action : {self.original_action}",
            f"Blocked at      : TIER {self.denied_tier.value}",
            "",
            "Alternatives:",
        ]
        for i, alt in enumerate(self.alternatives, 1):
            lines.append(f"  {i}. {alt.title}")
            lines.append(f"     {alt.description}")
            if alt.pros:
                lines.append("     ✓ " + "; ".join(alt.pros))
            if alt.cons:
                lines.append("     ✗ " + "; ".join(alt.cons))
        return "\n".join(lines)


class FallbackStrategies:
    """Propose alternative approaches when a permission is denied."""

    # ── Built-in rule-based alternatives ──────────────────────────────────

    _RULES: dict = {
        PermissionTier.FULL_SYSTEM: [
            Alternative(
                title="Generate Python automation script instead",
                description=(
                    "Create a self-contained Python script that replicates "
                    "the shell script behaviour."
                ),
                pros=["Cross-platform", "Testable", "No shell access needed"],
                cons=["Not native bash", "Requires Python interpreter"],
                min_tier=PermissionTier.CODE_EXEC,
            ),
            Alternative(
                title="Show commands for manual execution",
                description=(
                    "Output the exact commands the user can copy-paste "
                    "into their terminal."
                ),
                pros=["User stays in control", "No permissions needed"],
                cons=["Requires manual steps"],
                min_tier=PermissionTier.BASIC,
            ),
        ],
        PermissionTier.SELF_MODIFY: [
            Alternative(
                title="Generate a patch file for manual review and application",
                description=(
                    "Produce a unified diff the user can apply with `git apply` "
                    "or patch(1)."
                ),
                pros=["User reviews before applying", "Fully reversible"],
                cons=["Requires manual application"],
                min_tier=PermissionTier.BASIC,
            ),
            Alternative(
                title="Write improved code to a new file",
                description=(
                    "Save the improved version alongside the original "
                    "(e.g. `module_improved.py`) so the user can compare."
                ),
                pros=["Non-destructive", "Easy comparison"],
                cons=["Original is not modified automatically"],
                min_tier=PermissionTier.FILE_WRITE,
            ),
        ],
        PermissionTier.FILE_WRITE: [
            Alternative(
                title="Print the content for copy-paste",
                description="Display the file content in the terminal for manual saving.",
                pros=["No permissions needed", "User controls where it is saved"],
                cons=["Requires manual copy-paste"],
                min_tier=PermissionTier.BASIC,
            ),
        ],
        PermissionTier.CODE_EXEC: [
            Alternative(
                title="Validate and display the code without running it",
                description=(
                    "Run static analysis and show the expected output based "
                    "on code analysis."
                ),
                pros=["Safe", "No execution environment needed"],
                cons=["Cannot show real runtime output"],
                min_tier=PermissionTier.BASIC,
            ),
        ],
    }

    def get_alternatives(
        self,
        denied_tier: PermissionTier,
        original_action: str,
        granted_tier: PermissionTier = PermissionTier.BASIC,
    ) -> FallbackPlan:
        """Return a FallbackPlan for the given denied tier.

        Only includes alternatives whose `min_tier` is <= *granted_tier*.
        """
        candidates = self._RULES.get(denied_tier, [])
        filtered   = [a for a in candidates if a.min_tier <= granted_tier]

        # If nothing matches the built-in rules, use the LLM as a fallback
        if not filtered:
            filtered = self._llm_alternatives(denied_tier, original_action, granted_tier)

        return FallbackPlan(
            original_action=original_action,
            denied_tier=denied_tier,
            alternatives=filtered,
        )

    # ── LLM fallback ──────────────────────────────────────────────────────

    @staticmethod
    def _llm_alternatives(
        denied_tier: PermissionTier,
        original_action: str,
        granted_tier: PermissionTier,
    ) -> List[Alternative]:
        """Ask the LLM for creative alternatives when no built-in rule matches."""
        from lirox.utils.llm import generate_response

        prompt = (
            f"The user denied TIER {denied_tier.value} permission.\n"
            f"Original action: {original_action}\n"
            f"Current max permission tier: TIER {granted_tier.value}.\n\n"
            "Suggest 2 practical alternative approaches that stay within "
            f"TIER {granted_tier.value}. For each give:\n"
            "  title: one-line name\n"
            "  description: one sentence\n"
            "  pros: comma-separated advantages\n"
            "  cons: comma-separated disadvantages\n\n"
            "Reply as a numbered list."
        )
        try:
            raw = generate_response(
                prompt, provider="auto",
                system_prompt="You are a helpful AI suggesting creative workarounds.",
            )
            # Parse simple numbered list into Alternative objects
            alts: List[Alternative] = []
            for block in raw.split("\n\n"):
                block = block.strip()
                if block:
                    lines = block.splitlines()
                    title = lines[0].lstrip("0123456789. ").strip()
                    desc  = lines[1].strip() if len(lines) > 1 else ""
                    alts.append(Alternative(
                        title=title, description=desc,
                        min_tier=granted_tier,
                    ))
                    if len(alts) >= 2:
                        break
            return alts
        except Exception:
            return []
