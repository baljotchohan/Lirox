"""
Lirox v2.0 — Reasoner

Evaluates plan step results, detects errors, determines retry/skip/abort
actions, and reflects on overall plan progress.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List


# Keywords that indicate a retryable (transient) failure
_RETRY_KEYWORDS = ["timeout", "timed out", "connection", "rate limit", "503", "network", "server error"]


class Reasoner:
    """
    Reasons about plan execution: evaluates step results, reflects on
    progress, and generates human-readable summaries.
    """

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.evaluations: List[Dict[str, Any]] = []
        self.last_reasoning: Optional[str] = None
        self.last_reasoning_text: str = ""

    def evaluate_step(
        self,
        step: Dict[str, Any],
        result: Dict[str, Any],
        plan: Dict[str, Any],
        completed_steps: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate whether a step succeeded and what to do next.

        Returns dict with:
          - success: bool
          - confidence: float (0.0–1.0)
          - recommended_action: "continue" | "retry" | "skip" | "abort"
          - reason: str
        """
        status = result.get("status", "")
        output = result.get("output", "")
        error  = result.get("error", "")

        success = status == "success"

        if success:
            # Basic confidence: does output look like something meaningful?
            confidence = 0.9 if len(str(output)) > 10 else 0.5
            action = "continue"
            reason = "Step completed successfully."
        else:
            confidence = 0.1
            error_str = (str(error) + str(output)).lower()

            # Determine if transient error worth retrying
            if any(kw in error_str for kw in _RETRY_KEYWORDS):
                action = "retry"
                reason = f"Transient failure detected: {error or output}"
            else:
                action = "skip"
                reason = f"Non-recoverable failure: {error or output}"

        evaluation = {
            "step_id":            step.get("id"),
            "task":               step.get("task", ""),
            "success":            success,
            "confidence":         confidence,
            "recommended_action": action,
            "reason":             reason,
        }
        self.evaluations.append(evaluation)
        self.last_reasoning = reason

        # Update human-readable text
        self.last_reasoning_text = self._build_reasoning_text()

        return evaluation

    def reflect_on_progress(
        self,
        plan: Dict[str, Any],
        results: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Reflect on overall plan progress.

        Returns:
          - completed: int
          - remaining: int
          - on_track: bool
          - summary: str
        """
        total_steps = len(plan.get("steps", []))
        completed   = len(results)
        remaining   = total_steps - completed

        successes = sum(1 for r in results.values() if r.get("status") == "success")
        on_track  = successes == completed  # All completed steps were successful

        return {
            "completed": completed,
            "remaining": remaining,
            "on_track":  on_track,
            "total":     total_steps,
            "summary":   f"{completed}/{total_steps} steps done. {'On track.' if on_track else 'Issues detected.'}",
        }

    def generate_reasoning_summary(
        self,
        plan: Dict[str, Any],
        results: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate a structured reasoning summary of the full plan execution.
        """
        reflection = self.reflect_on_progress(plan, results)

        summary = {
            "goal":        plan.get("goal", ""),
            "evaluations": [dict(e) for e in self.evaluations],
            "progress":    reflection,
            "overall_success": reflection["on_track"],
        }

        # Build human-readable text
        lines = [
            "Reasoning Summary",
            "=" * 40,
            f"Goal: {plan.get('goal', '')}",
            f"Progress: {reflection['completed']}/{reflection['total']} steps",
            "",
        ]
        for ev in self.evaluations:
            status_icon = "✅" if ev["success"] else "❌"
            lines.append(
                f"{status_icon} Step {ev['step_id']}: {ev['task']} — {ev['recommended_action']}"
            )

        self.last_reasoning_text = "\n".join(lines)

        return summary

    def reset(self) -> None:
        """Clear all evaluation state."""
        self.evaluations = []
        self.last_reasoning = None
        self.last_reasoning_text = ""

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_reasoning_text(self) -> str:
        lines = ["Reasoning Summary", "=" * 40]
        for ev in self.evaluations:
            icon = "✅" if ev["success"] else "❌"
            lines.append(f"{icon} Step {ev['step_id']}: {ev['task']} — {ev['reason']}")
        return "\n".join(lines)
