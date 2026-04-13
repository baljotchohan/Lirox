"""Multi-phase reasoning: UNDERSTAND → STRATEGIZE → PLAN"""
from lirox.utils.llm import generate_response
from lirox.config import MAX_CONTEXT_CHARS, MAX_TOOL_RESULT_CHARS


class ThinkingEngine:
    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.last_trace = ""

    def reason(self, query: str, context: str = "") -> str:
        prompt = f"""Structured reasoning for this query:

Query: {query}
{f"Context: {context[:MAX_CONTEXT_CHARS]}" if context else ""}

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
        except Exception as e:
            import logging
            logging.getLogger("lirox.thinking").warning(
                f"ThinkingEngine.reason failed, returning minimal trace: {e}"
            )
            self.last_trace = f"UNDERSTAND: {query}"
            return self.last_trace

    def reason_deep(self, query: str, context: str = "") -> str:
        """Multi-path deep reasoning with approach comparison.

        Falls back to :meth:`reason` if the advanced reasoning module is
        unavailable or the LLM call fails.
        """
        try:
            from lirox.thinking.advanced_reasoning import AdvancedReasoning
            trace = AdvancedReasoning().reason_deep(query)
            self.last_trace = trace
            return trace
        except Exception:
            return self.reason(query, context)

