"""Lirox Autonomy — Autonomous Resolver.

Orchestrates the full autonomy subsystem:
  1. Permission checking / requesting
  2. Deep thinking & problem decomposition
  3. Code intelligence & generation
  4. Validation & testing
  5. Self-improvement
  6. Fallback strategies

Yields structured events that the orchestrator/UI layers consume.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Generator, Optional

from lirox.autonomy.permission_system import (
    PermissionSystem,
    PermissionTier,
    PermissionRequest,
)


EventStream = Generator[Dict[str, Any], None, None]


class AutonomousResolver:
    """High-level entry point for the autonomy subsystem."""

    def __init__(
        self,
        permission_system: Optional[PermissionSystem] = None,
        user_confirm_fn: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.permissions    = permission_system or PermissionSystem()
        self._confirm       = user_confirm_fn  # blocking console prompt, or None

    # ── Permission helpers ─────────────────────────────────────────────────

    def ensure_permission(
        self,
        tier: PermissionTier,
        reason: str,
        action: str,
        alternatives: list = None,
    ) -> Generator[Dict[str, Any], None, bool]:
        """Yield permission events; return True if permission is available.

        This is a generator—callers must iterate it before reading the return
        value (use `yield from` with send pattern, or collect events manually).
        """
        if self.permissions.has_permission(tier):
            return True

        req = PermissionRequest(
            tier=tier,
            reason=reason,
            action=action,
            alternatives=alternatives or [],
        )

        # Yield the request event for the UI to render
        for ev in self.permissions.request_events(req):
            yield {"type": ev.type, "message": ev.message, "data": ev.data}

        # If we have a blocking confirm function, use it now
        if self._confirm is not None:
            granted = self._confirm(f"Allow TIER {tier.value} permission?")
            if granted:
                ev = self.permissions.process_grant(tier)
            else:
                ev = self.permissions.process_deny(tier)
            yield {"type": ev.type, "message": ev.message}
            return granted

        # Without a confirm function the caller must handle via send()
        return False

    # ── High-level tasks ───────────────────────────────────────────────────

    def resolve_code_generation(
        self, description: str, save_path: str = ""
    ) -> EventStream:
        """Full code-generation pipeline with permission checks."""
        yield {"type": "deep_thinking", "message": "🧠 Analysing requirements…"}

        # Decompose the problem
        from lirox.thinking.problem_decomposer import ProblemDecomposer
        decomposer = ProblemDecomposer()
        steps      = decomposer.decompose(description)
        if steps:
            yield {
                "type":    "deep_thinking",
                "message": "Decomposed into steps:\n" + "\n".join(
                    f"  {i}. {s}" for i, s in enumerate(steps, 1)
                ),
            }

        # Gather codebase context
        yield {"type": "code_analysis", "message": "📖 Reading project style…"}
        from lirox.autonomy.code_intelligence import CodeIntelligence
        ci    = CodeIntelligence()
        style = ci.detect_style()

        # Generate code
        yield {"type": "code_generation", "message": "✍ Generating code…"}
        from lirox.autonomy.code_generator import AutoCodeGenerator
        gen  = AutoCodeGenerator(style=style)
        code = gen.generate_from_description(description)

        # Validate
        yield {"type": "code_validation", "message": "🔍 Validating generated code…"}
        from lirox.autonomy.code_validator import CodeValidator
        vr = CodeValidator().validate(code)
        if not vr.valid:
            yield {
                "type":    "code_validation",
                "message": "⚠ Validation issues:\n" + "\n".join(vr.errors),
            }
        if vr.warnings:
            yield {
                "type":    "code_validation",
                "message": "Warnings:\n" + "\n".join(vr.warnings),
            }

        # Save if path provided and permission exists
        if save_path and self.permissions.has_permission(PermissionTier.FILE_WRITE):
            yield {"type": "step_execution", "message": f"💾 Saving to {save_path}…"}
            from pathlib import Path
            try:
                Path(save_path).expanduser().write_text(code, encoding="utf-8")
                yield {"type": "step_execution", "message": f"✓ Saved: {save_path}"}
            except OSError as exc:
                yield {"type": "error", "message": f"Save failed: {exc}"}

        yield {
            "type":    "done",
            "message": code,
            "answer":  code,
        }

    def resolve_self_improvement(self) -> EventStream:
        """Full self-improvement pipeline."""
        if not self.permissions.has_permission(PermissionTier.SELF_MODIFY):
            yield {
                "type":    "permission_request",
                "message": (
                    "🔬 Self-modification requires TIER 5 permission.\n"
                    "Use /ask-permission 5 to grant it."
                ),
            }
            return

        yield {"type": "self_improvement", "message": "🔬 Starting self-audit…"}

        from lirox.autonomy.self_improver import SelfImprover
        improver = SelfImprover()

        # Stream scan progress
        for ev in improver.scan_events():
            yield ev

        issues = improver._issues
        if not issues:
            yield {"type": "self_improvement", "message": "✓ No issues found."}
            return

        yield {
            "type":    "self_improvement",
            "message": f"Found {len(issues)} issue(s). Generating patches…",
        }
        yield {"type": "code_generation", "message": "Generating patches…"}
        patches = improver.generate_patches()

        if not patches:
            yield {"type": "self_improvement", "message": "No patches generated."}
            return

        diffs = "\n\n".join(p.diff for p in patches)
        yield {
            "type":    "self_improvement",
            "message": f"✓ {len(patches)} patch(es) ready.",
            "data":    {"patches": patches, "diffs": diffs},
        }

    def resolve_fallback(
        self,
        original_action: str,
        denied_tier: PermissionTier,
    ) -> EventStream:
        """Yield fallback alternatives when permission is denied."""
        from lirox.autonomy.fallback_strategies import FallbackStrategies
        plan = FallbackStrategies().get_alternatives(
            denied_tier=denied_tier,
            original_action=original_action,
            granted_tier=self.permissions.current_max_tier(),
        )
        yield {
            "type":    "fallback",
            "message": plan.summary(),
            "data":    {"plan": plan},
        }
