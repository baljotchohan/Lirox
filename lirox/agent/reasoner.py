"""
Lirox v0.5 — Reasoner (Thinking Loop)

Provides intelligent inter-step evaluation:
- Evaluate step success/failure with confidence
- Reflect on overall plan progress
- Analyze failures and recommend actions
- Generate reasoning summaries for user inspection

Fixes from v0.4:
- last_reasoning_text initialized in __init__ (was causing AttributeError)
"""

from lirox.utils.llm import generate_response


class Reasoner:
    """Intelligent reasoning engine for evaluating plan execution."""

    def __init__(self, provider: str = "auto"):
        self.provider          = provider
        self.last_reasoning    = None
        self.last_reasoning_text = ""   # Fix: initialize so /reasoning never throws AttributeError
        self.evaluations       = []
        self.thought_trace     = ""

    def set_provider(self, provider: str):
        self.provider = provider

    def generate_thought_trace(self, goal: str, context: str = "") -> str:
        """Produce a detailed logical breakdown (Phase-based thinking)."""
        prompt = (
            f"You are the strategic reasoning core of Lirox.\n"
            f"Analyze the following goal and break down your internal logic into three distinct phases.\n\n"
            f"Goal: {goal}\n"
            f"Context: {context or 'None'}\n\n"
            f"MANDATORY OUTPUT FORMAT:\n"
            f"PHASE 1: STRATEGIC ANALYSIS\n"
            f"(Analyze the core requirements and system state)\n\n"
            f"PHASE 2: EXECUTION LOGIC\n"
            f"(Steps, tools, and technical approach)\n\n"
            f"PHASE 3: RISK & CONTINGENCY\n"
            f"(Anticipated obstacles and how to bypass them)\n\n"
            f"Be deep, technical, and logical. Use bullet points."
        )
        try:
            self.thought_trace = generate_response(
                prompt, self.provider,
                system_prompt="You are a brilliant, logical AI strategist. "
                              "Break your logic into Phase 1, Phase 2, and Phase 3 exactly."
            )
            return self.thought_trace
        except Exception:
            self.thought_trace = f"PHASE 1: ANALYSIS\n- Thinking about how to resolve: {goal}..."
            return self.thought_trace

    def evaluate_step(self, step: dict, result: dict, plan: dict, all_results: dict) -> dict:
        """
        Evaluate a step result and decide what to do next.

        Returns: Evaluation dict with success status and recommended action.
        """
        success = result.get("status") == "success"
        output  = result.get("output", "")

        evaluation = {
            "step_id":            step["id"],
            "task":               step["task"],
            "success":            success,
            "confidence":         0.0,
            "notes":              "",
            "recommended_action": "continue",
        }

        if success:
            evaluation["confidence"]         = self._assess_confidence(step, output)
            evaluation["notes"]              = "Step completed successfully"
            evaluation["recommended_action"] = "continue"
        else:
            analysis = self._analyze_failure(step, result)
            evaluation["confidence"]         = 0.1
            evaluation["notes"]              = analysis.get("analysis", "Step failed")
            evaluation["recommended_action"] = analysis.get("action", "skip")

        self.evaluations.append(evaluation)
        return evaluation

    def _assess_confidence(self, step: dict, output: str) -> float:
        if not output or output.strip() == "":
            return 0.3

        expected     = step.get("expected_output", "").lower()
        output_lower = output.lower()

        error_indicators = ["error", "failed", "exception", "traceback", "blocked"]
        if any(e in output_lower for e in error_indicators):
            return 0.2

        if expected and len(expected) > 5:
            expected_words = set(expected.split())
            output_words   = set(output_lower.split())
            overlap = len(expected_words & output_words) / max(len(expected_words), 1)
            return min(0.5 + overlap * 0.5, 1.0)

        return 0.7

    def _analyze_failure(self, step: dict, result: dict) -> dict:
        output       = result.get("output", "")
        error        = result.get("error", "")
        failure_text = error or output
        failure_lower = failure_text.lower()

        if any(p in failure_lower for p in ["timeout", "timed out", "rate limit", "429"]):
            return {"analysis": f"Transient error: {failure_text[:100]}", "action": "retry"}

        if any(p in failure_lower for p in ["access denied", "blocked", "permission"]):
            return {"analysis": f"Permission error: {failure_text[:100]}", "action": "skip"}

        if any(p in failure_lower for p in ["not found", "404", "no such file"]):
            return {"analysis": f"Resource not found: {failure_text[:100]}", "action": "skip"}

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
            analysis = "Unknown failure"
            action   = "skip"
            for line in response.split("\n"):
                if line.strip().upper().startswith("ANALYSIS:"):
                    analysis = line.split(":", 1)[1].strip()
                elif line.strip().upper().startswith("ACTION:"):
                    raw = line.split(":", 1)[1].strip().lower()
                    action = raw if raw in ("retry", "skip") else "skip"
            return {"analysis": analysis, "action": action}
        except Exception:
            return {"analysis": f"Step failed: {failure_text[:100]}", "action": "skip"}

    def reflect_on_progress(self, plan: dict, results_so_far: dict) -> dict:
        total_steps = len(plan["steps"])
        completed   = sum(1 for r in results_so_far.values() if r.get("status") == "success")
        failed      = sum(1 for r in results_so_far.values() if r.get("status") == "failed")

        reflection = {
            "progress":        f"{completed}/{total_steps} steps complete",
            "completion_pct":  round(completed / max(total_steps, 1) * 100),
            "on_track":        failed <= 1,
            "completed":       completed,
            "failed":          failed,
            "remaining":       total_steps - len(results_so_far),
            "issues_detected": [],
        }

        if failed > 0:
            reflection["issues_detected"].append(f"{failed} step(s) failed")
        if failed >= total_steps * 0.5:
            reflection["issues_detected"].append("⚠️ High failure rate — plan may need revision")
            reflection["on_track"] = False

        return reflection

    def generate_reasoning_summary(self, plan: dict, all_results: dict) -> dict:
        eval_list = [
            {
                "step_id":    e["step_id"],
                "task":       e["task"],
                "success":    e["success"],
                "confidence": e["confidence"],
                "action":     e["recommended_action"],
                "notes":      e["notes"],
            }
            for e in self.evaluations
        ]

        reflection = self.reflect_on_progress(plan, all_results)
        avg_conf   = sum(e["confidence"] for e in eval_list) / max(len(eval_list), 1)
        reflection["overall_confidence"] = round(avg_conf, 2)

        if reflection["failed"] > 0 and avg_conf < 0.5:
            reflection["suggestion"] = (
                "Consider retrying with a more powerful model or clarifying the instructions."
            )
        else:
            reflection["suggestion"] = "Execution appears solid. No immediate correction needed."

        self.last_reasoning = {"evaluations": eval_list, "reflection": reflection}

        text_lines = [f"### 💭 Reasoning Summary | Confidence: {int(avg_conf*100)}%", ""]
        for e in eval_list:
            icon = "✓" if e["success"] else "✗"
            text_lines.append(f"- **{icon}** {e['task'][:50]}... (**{int(e['confidence']*100)}%**)")

        text_lines.append("")
        text_lines.append(f"**Current Status**: {reflection['progress']}")
        text_lines.append(f"**Final Suggestion**: {reflection['suggestion']}")

        self.last_reasoning_text = "\n".join(text_lines)
        return self.last_reasoning

    def get_last_reasoning(self):
        return self.last_reasoning or "No reasoning data yet. Run a task first."

    def reset(self):
        self.evaluations   = []
        self.last_reasoning = None
