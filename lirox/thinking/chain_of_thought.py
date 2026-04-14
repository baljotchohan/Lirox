"""Multi-phase reasoning: UNDERSTAND → STRATEGIZE → PLAN"""
from lirox.utils.llm import generate_response
from lirox.config import MAX_CONTEXT_CHARS, MAX_TOOL_RESULT_CHARS


class ThinkingEngine:
    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.last_trace = ""

    def reason(self, query: str, context: str = "") -> str:
        prompt = f"""Structured reasoning:

Query: {query}
{f"Context: {context[:MAX_CONTEXT_CHARS]}" if context else ""}

UNDERSTAND: What is really being asked? What are the unstated needs?
STRATEGIZE: What's the best approach? What tools or knowledge are needed?
RISKS: What could go wrong? What assumptions am I making?
PLAN: 3-5 concrete steps.

Be concise. Focus on actionable insight."""
        try:
            self.last_trace = generate_response(
                prompt,
                self.provider,
                system_prompt="Strategic reasoning engine. Direct. Precise. No fluff.",
            )
            return self.last_trace
        except Exception as e:
            import logging
            logging.getLogger("lirox.thinking").warning(f"ThinkingEngine.reason failed: {e}")
            self.last_trace = f"UNDERSTAND: {query}"
            return self.last_trace

    def reason_deep(self, query: str, context: str = "") -> str:
        """
        Multi-path deep reasoning with approach comparison.
        Used for complex architecture, design, and strategy questions.
        """
        try:
            from lirox.thinking.advanced_reasoning import AdvancedReasoning
            import re
            ar = AdvancedReasoning()
            trace = ar.reason_deep(query)

            # Score and rank the approaches found
            approaches = re.findall(r"^\d+\.\s+\[([^\]]+)\]", trace, re.MULTILINE)
            if len(approaches) >= 2:
                scored = sorted(approaches, key=lambda a: ar.score_approach(a, context) if hasattr(ar, 'score_approach') else 0, reverse=True)
                trace += f"\n\n**Quality-ranked approaches:** {' > '.join(scored[:3])}"

            self.last_trace = trace
            return trace
        except Exception:
            return self.reason(query, context)

    def reason_creative(self, query: str) -> str:
        """
        Lateral thinking mode for creative, open-ended problems.
        Generates unexpected angles and contrarian approaches.
        """
        prompt = f"""Creative problem-solving for: {query}

Generate 3 UNEXPECTED approaches that most people wouldn't consider:

1. [Contrarian]: What if we did the opposite of the obvious?
2. [Constraint removal]: What if the main constraint didn't exist?
3. [Adjacent domain]: How does a completely different field solve this?

Then: What's the BOLDEST version of this idea?

Be creative. Surprising. Useful."""
        try:
            result = generate_response(
                prompt, self.provider,
                system_prompt="Creative lateral thinking engine. Be genuinely surprising."
            )
            self.last_trace = result
            return result
        except Exception:
            return self.reason(query)

