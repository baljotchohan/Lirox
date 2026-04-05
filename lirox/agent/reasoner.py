"""Lirox v2.0 — Agent Reasoner

Evaluates individual step results and reflects on overall plan progress.
Operates without LLM calls — all reasoning is heuristic/rule-based for speed
and determinism, while still storing a human-readable reasoning trace.
"""

from typing import Any, Dict, List, Optional


class Reasoner:
    """
    Heuristic step evaluator and plan-progress reflector.

    Attributes:
        evaluations: list of per-step evaluation dicts
        last_reasoning: the most recent evaluation dict (or None)
        last_reasoning_text: human-readable summary text (updated after
                             generate_reasoning_summary() is called)
    """

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.evaluations: List[Dict[str, Any]] = []
        self.last_reasoning: Optional[Dict[str, Any]] = None
        self.last_reasoning_text: str = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate_step(
        self,
        step: Dict[str, Any],
        result: Dict[str, Any],
        plan: Dict[str, Any],
        results_so_far: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate a single step result and return an evaluation dict.

        Returns a dict with:
            success (bool)
            confidence (float 0–1)
            recommended_action (str): "continue" | "retry" | "skip" | "abort"
            reason (str)
        """
        status = result.get("status", "unknown")
        output = result.get("output", "") or ""
        error = result.get("error", "") or ""
        expected = step.get("expected_output", "")

        success = status == "success"
        confidence = self._compute_confidence(success, output, expected, error)
        action = self._recommend_action(success, error, confidence)

        evaluation = {
            "step_id": step.get("id"),
            "task": step.get("task", ""),
            "success": success,
            "confidence": confidence,
            "recommended_action": action,
            "reason": self._build_reason(success, error, action),
        }
        self.evaluations.append(evaluation)
        self.last_reasoning = evaluation
        return evaluation

    def reflect_on_progress(
        self,
        plan: Dict[str, Any],
        results: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Reflect on how much of the plan has been completed.

        Returns:
            completed (int): number of successfully completed steps
            remaining (int): number of steps not yet done
            on_track (bool): True when ≥50 % of completed steps succeeded
            progress_pct (float): 0–100
        """
        all_steps = plan.get("steps", [])
        total = len(all_steps)
        completed_ids = {sid for sid, r in results.items() if r.get("status") == "success"}
        completed = len(completed_ids)
        remaining = total - len(results)

        progress_pct = (completed / total * 100) if total > 0 else 0.0
        on_track = completed >= (len(results) / 2) if results else True

        return {
            "total": total,
            "completed": completed,
            "remaining": max(remaining, 0),
            "progress_pct": round(progress_pct, 1),
            "on_track": on_track,
        }

    def generate_reasoning_summary(
        self,
        plan: Dict[str, Any],
        results: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate a structured summary of all reasoning done so far.

        Also sets `last_reasoning_text` with a human-readable version.
        """
        goal = plan.get("goal", "unknown goal")
        lines = [f"## Reasoning Summary for: {goal}"]

        for ev in self.evaluations:
            status_icon = "✓" if ev["success"] else "✗"
            lines.append(
                f"  {status_icon} Step {ev['step_id']}: {ev['task']} "
                f"— {ev['recommended_action']} (confidence: {ev['confidence']:.2f})"
            )

        self.last_reasoning_text = "\n".join(lines)

        return {
            "goal": goal,
            "evaluations": list(self.evaluations),
            "summary_text": self.last_reasoning_text,
        }

    def reset(self) -> None:
        """Clear all stored evaluations and reasoning state."""
        self.evaluations = []
        self.last_reasoning = None
        self.last_reasoning_text = ""

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _compute_confidence(
        self, success: bool, output: str, expected: str, error: str
    ) -> float:
        if not success:
            if any(k in error.lower() for k in ["timeout", "timed out", "connection"]):
                return 0.4  # Transient — worth retrying
            return 0.1

        base = 0.7
        if expected and expected.lower() in output.lower():
            base += 0.2
        if len(output) > 50:
            base += 0.1
        return min(base, 1.0)

    def _recommend_action(self, success: bool, error: str, confidence: float) -> str:
        if success:
            return "continue"
        error_lower = error.lower()
        if any(k in error_lower for k in ["timeout", "timed out", "connection", "network", "retry"]):
            return "retry"
        if confidence < 0.2:
            return "abort"
        return "skip"

    def _build_reason(self, success: bool, error: str, action: str) -> str:
        if success:
            return "Step completed successfully."
        if error:
            return f"Step failed: {error}. Recommended action: {action}."
        return f"Step failed with no error details. Recommended action: {action}."
