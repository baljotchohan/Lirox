"""Lirox Autonomy — Autonomous Resolver.

Orchestrates the full autonomy subsystem:
  1. Permission checking / requesting
  2. Deep thinking & problem decomposition
  3. Code intelligence & generation
  4. Validation & testing
  5. Self-improvement
  6. Fallback strategies

Yields structured events for the orchestrator/UI layers to consume.
No external APIs or network calls.
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
        self.permissions = permission_system or PermissionSystem()
        self._confirm    = user_confirm_fn  # blocking console prompt, or None

    # ── Permission helpers ─────────────────────────────────────────────────

    def _require_permission(
        self,
        tier: PermissionTier,
        reason: str,
        action: str,
        alternatives: list = None,
    ) -> Generator[Dict[str, Any], bool, None]:
        """Internal generator: yield request event, return bool (has permission).

        Usage pattern (inside another generator):
            ok = yield from self._require_permission(...)
            if not ok:
                return
        """
        if self.permissions.has_permission(tier):
            return True

        req = PermissionRequest(
            tier=tier, reason=reason, action=action,
            alternatives=alternatives or [],
        )
        for ev in self.permissions.request_events(req):
            yield {"type": ev.type, "message": ev.message, "data": ev.data}

        # If a user-confirm callback is provided, ask interactively
        if self._confirm is not None:
            if self._confirm(f"Grant {req.label}? (y/n): "):
                grant_ev = self.permissions.grant_event(tier)
                yield {"type": grant_ev.type, "message": grant_ev.message,
                       "data": grant_ev.data}
                return True
            else:
                deny_ev = self.permissions.deny_event(tier, alternatives or [])
                yield {"type": deny_ev.type, "message": deny_ev.message,
                       "data": deny_ev.data}
                return False

        # No callback — just emit the deny event
        deny_ev = self.permissions.deny_event(tier, alternatives or [])
        yield {"type": deny_ev.type, "message": deny_ev.message, "data": deny_ev.data}
        return False

    # ── Code generation pipeline ───────────────────────────────────────────

    def resolve_code_generation(self, description: str) -> EventStream:
        """Generate, validate, and optionally test code for *description*."""
        yield {"type": "code_generation", "message": "🧠 Starting code generation…"}

        # No permission needed for pure generation
        from lirox.autonomy.code_generator import CodeGenerator
        from lirox.autonomy.code_validator import CodeValidator

        generator = CodeGenerator()
        validator = CodeValidator()

        yield {"type": "code_generation", "message": "✍️  Generating code…"}
        try:
            result = generator.generate(description, validate=False)
        except Exception as exc:
            yield {"type": "code_generation",
                   "message": f"Generation failed: {exc}"}
            return

        code = result.get("code", "")
        if not code:
            yield {"type": "code_generation", "message": "No code produced."}
            return

        # Validation (pure Python — no execution, no permission needed)
        vr = validator.check_syntax(code)
        if vr.valid:
            yield {"type": "code_generation", "message": "✓ Syntax valid"}
        else:
            for err in vr.errors:
                yield {"type": "code_generation", "message": f"  ✖ {err}"}

        sec = validator.security_scan(code)
        for w in sec.warnings:
            yield {"type": "code_generation", "message": f"  ⚠ {w}"}

        yield {"type": "streaming", "message": f"```python\n{code}\n```"}
        yield {"type": "done", "answer": f"```python\n{code}\n```"}

    # ── Self-improvement pipeline ──────────────────────────────────────────

    def resolve_self_improvement(self) -> EventStream:
        """Scan the Lirox codebase for issues and report findings."""
        yield {"type": "self_improvement", "message": "🔬 Starting self-improvement scan…"}

        from lirox.config import PROJECT_ROOT
        from pathlib import Path
        from lirox.autonomy.self_improver import SelfImprover

        lirox_dir = str(Path(PROJECT_ROOT) / "lirox")

        improver = SelfImprover()
        yield from improver.analyse_and_stream(lirox_dir)

        summary = improver.get_improvement_summary(lirox_dir)
        yield {"type": "self_improvement", "message": summary}
        yield {"type": "done", "answer": summary}

    # ── Analysis pipeline ──────────────────────────────────────────────────

    def resolve_code_analysis(self, query: str = "") -> EventStream:
        """Run AST-based project analysis and stream results."""
        yield {"type": "code_analysis", "message": "📖 Scanning project…"}

        from lirox.autonomy.code_intelligence import CodeIntelligence

        ci      = CodeIntelligence()
        summary = ci.summary()
        yield {"type": "code_analysis", "message": summary}
        yield {"type": "done", "answer": summary}

    # ── Fallback pipeline ──────────────────────────────────────────────────

    def resolve_fallback(
        self,
        blocked_tier: PermissionTier,
        task_description: str,
        original_error: str = "",
    ) -> EventStream:
        """Generate fallback suggestions when an action is blocked."""
        from lirox.autonomy.fallback_strategies import FallbackStrategies
        yield from FallbackStrategies().stream_fallback(
            blocked_tier, task_description, original_error
        )
