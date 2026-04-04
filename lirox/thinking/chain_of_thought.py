"""Multi-phase reasoning: UNDERSTAND → STRATEGIZE → PLAN"""
from lirox.utils.llm import generate_response


class ThinkingEngine:
    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.last_trace = ""

    def reason(self, query: str, context: str = "") -> str:
        prompt = f"""Structured reasoning for this query:

Query: {query}
{f"Context: {context[:2000]}" if context else ""}

UNDERSTAND: What is being asked? Key requirements?
STRATEGIZE: Best approach? Tools needed? Risks?
PLAN: 3-5 step action plan.

Be concise."""
        try:
            self.last_trace = generate_response(
                prompt,
                self.provider,
                system_prompt="Strategic reasoning engine. Concise and precise.",
            )
            return self.last_trace
        except Exception:
            self.last_trace = f"UNDERSTAND: {query}"
            return self.last_trace

    def reflect(self, query: str, result: str) -> str:
        try:
            return generate_response(
                f"Rate 1-10. Complete? Accurate?\nQuery: {query}\nResult: {result[:3000]}",
                self.provider,
                system_prompt="Brief quality evaluator.",
            )
        except Exception:
            return "Reflection unavailable."
