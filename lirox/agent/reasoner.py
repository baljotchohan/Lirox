"""
Lirox v0.3 — Reasoner (Thinking Loop)

Provides intelligent inter-step evaluation:
- Evaluate step success/failure with confidence
- Reflect on overall plan progress
- Analyze failures and recommend actions
- Generate reasoning summaries for user inspection
"""

from lirox.utils.llm import generate_response


class Reasoner:
    """Intelligent reasoning engine for evaluating plan execution."""

    def __init__(self, provider="groq"):
        self.provider = provider
        self.last_reasoning = None  # Store for /reasoning command
        self.evaluations = []       # All step evaluations this session

    def set_provider(self, provider):
        self.provider = provider

    def evaluate_step(self, step, result, plan, all_results):
        """
        Evaluate a step result and decide what to do next.

        Args:
            step: Step dict from plan
            result: Step execution result dict {"status": ..., "output": ...}
            plan: Full plan dict
            all_results: Dict of {step_id: result} for all completed steps

        Returns:
            Evaluation dict with success status and recommended action
        """
        success = result.get("status") == "success"
        output = result.get("output", "")

        evaluation = {
            "step_id": step["id"],
            "task": step["task"],
            "success": success,
            "confidence": 0.0,
            "notes": "",
            "recommended_action": "continue"  # continue | retry | skip | modify_plan
        }

        if success:
            # Quick confidence check — did the output match expectations?
            evaluation["confidence"] = self._assess_confidence(step, output)
            evaluation["notes"] = "Step completed successfully"
            evaluation["recommended_action"] = "continue"
        else:
            # Analyze the failure
            analysis = self._analyze_failure(step, result)
            evaluation["confidence"] = 0.1
            evaluation["notes"] = analysis.get("analysis", "Step failed")
            evaluation["recommended_action"] = analysis.get("action", "skip")

        self.evaluations.append(evaluation)
        return evaluation

    def _assess_confidence(self, step, output):
        """
        Quick heuristic confidence score (0.0 to 1.0).
        Avoids an LLM call for simple checks.
        """
        if not output or output.strip() == "":
            return 0.3  # Empty output is suspicious

        expected = step.get("expected_output", "").lower()
        output_lower = output.lower()

        # Check if output contains error indicators
        error_indicators = ["error", "failed", "exception", "traceback", "blocked"]
        if any(e in output_lower for e in error_indicators):
            return 0.2

        # Check if expected keywords appear in output
        if expected and len(expected) > 5:
            expected_words = set(expected.split())
            output_words = set(output_lower.split())
            overlap = len(expected_words & output_words) / max(len(expected_words), 1)
            return min(0.5 + overlap * 0.5, 1.0)

        # Default: output exists and has no errors → decent confidence
        return 0.7

    def _analyze_failure(self, step, result):
        """
        Analyze why a step failed and recommend an action.
        Uses LLM for deeper analysis on non-obvious failures.
        """
        output = result.get("output", "")
        error = result.get("error", "")
        failure_text = error or output

        # Quick heuristic checks before LLM call
        failure_lower = failure_text.lower()

        if any(p in failure_lower for p in ["timeout", "timed out", "rate limit", "429"]):
            return {
                "analysis": f"Transient error detected: {failure_text[:100]}",
                "action": "retry"
            }

        if any(p in failure_lower for p in ["access denied", "blocked", "permission"]):
            return {
                "analysis": f"Permission/access error: {failure_text[:100]}",
                "action": "skip"
            }

        if any(p in failure_lower for p in ["not found", "404", "no such file"]):
            return {
                "analysis": f"Resource not found: {failure_text[:100]}",
                "action": "skip"
            }

        # For complex failures, use LLM
        try:
            prompt = (
                f"A task step failed. Analyze briefly and recommend ONE action.\n\n"
                f"Step: {step['task']}\n"
                f"Error: {failure_text[:300]}\n\n"
                f"Respond in this exact format:\n"
                f"ANALYSIS: (one sentence)\n"
                f"ACTION: retry OR skip"
            )
            response = generate_response(prompt, self.provider)
            
            # Parse response
            analysis = "Unknown failure"
            action = "skip"
            for line in response.split("\n"):
                if line.strip().upper().startswith("ANALYSIS:"):
                    analysis = line.split(":", 1)[1].strip()
                elif line.strip().upper().startswith("ACTION:"):
                    raw_action = line.split(":", 1)[1].strip().lower()
                    action = raw_action if raw_action in ("retry", "skip") else "skip"

            return {"analysis": analysis, "action": action}

        except Exception:
            return {
                "analysis": f"Step failed: {failure_text[:100]}",
                "action": "skip"
            }

    def reflect_on_progress(self, plan, results_so_far):
        """
        Mid-task reflection: assess overall plan progress.

        Args:
            plan: Full plan dict
            results_so_far: Dict of {step_id: result}

        Returns:
            Reflection dict with progress info and detected issues
        """
        total_steps = len(plan["steps"])
        completed = sum(1 for r in results_so_far.values() if r.get("status") == "success")
        failed = sum(1 for r in results_so_far.values() if r.get("status") == "failed")

        reflection = {
            "progress": f"{completed}/{total_steps} steps complete",
            "completion_pct": round(completed / max(total_steps, 1) * 100),
            "on_track": failed <= 1,  # Allow 1 failure before flagging
            "completed": completed,
            "failed": failed,
            "remaining": total_steps - len(results_so_far),
            "issues_detected": [],
        }

        if failed > 0:
            reflection["issues_detected"].append(f"{failed} step(s) failed")
        if failed >= total_steps * 0.5:
            reflection["issues_detected"].append("⚠️ High failure rate — plan may need revision")
            reflection["on_track"] = False

        return reflection

    def generate_reasoning_summary(self, plan, all_results):
        """
        Generate a human-readable reasoning summary of the plan execution.
        Stored for /reasoning command.

        Args:
            plan: Full plan dict
            all_results: Dict of {step_id: result}

        Returns:
            Formatted reasoning string
        """
        lines = ["💭 REASONING SUMMARY", ""]
        lines.append(f"Goal: {plan.get('goal', 'Unknown')}")
        lines.append(f"Steps: {len(plan['steps'])}")
        lines.append("")

        # Step-by-step reasoning
        for eval_data in self.evaluations:
            icon = "✓" if eval_data["success"] else "✗"
            confidence = int(eval_data["confidence"] * 100)
            lines.append(
                f"  {icon} Step {eval_data['step_id']}: {eval_data['task'][:60]}"
            )
            lines.append(
                f"    Confidence: {confidence}% | Action: {eval_data['recommended_action']}"
            )
            if eval_data["notes"] and eval_data["notes"] != "Step completed successfully":
                lines.append(f"    Note: {eval_data['notes'][:80]}")
            lines.append("")

        # Overall assessment
        reflection = self.reflect_on_progress(plan, all_results)
        lines.append(f"Progress: {reflection['progress']}")
        lines.append(f"On Track: {'Yes' if reflection['on_track'] else 'No'}")

        if reflection["issues_detected"]:
            lines.append("Issues: " + "; ".join(reflection["issues_detected"]))

        summary = "\n".join(lines)
        self.last_reasoning = summary
        return summary

    def get_last_reasoning(self):
        """Return the last reasoning summary for display."""
        return self.last_reasoning or "No reasoning data yet. Run a task first."

    def reset(self):
        """Reset evaluations for a new plan execution."""
        self.evaluations = []
        self.last_reasoning = None
