"""Multi-phase reasoning: UNDERSTAND → STRATEGIZE → PLAN

BUG-9 FIX: Added timeout with graceful degradation and output buffering.
All LLM calls are now wrapped with a configurable timeout (THINKING_TIMEOUT
env var, default 120s).  If the LLM times out, a partial/fallback result is
returned instead of hanging the terminal indefinitely.
"""
import logging
import concurrent.futures
from lirox.utils.llm import generate_response
from lirox.config import MAX_CONTEXT_CHARS, MAX_TOOL_RESULT_CHARS, THINKING_TIMEOUT


_log = logging.getLogger("lirox.thinking")


class ThinkingEngine:
    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.last_trace = ""
        self._timeout = THINKING_TIMEOUT  # BUG-9: configurable timeout

    def _generate_with_timeout(self, prompt: str, system_prompt: str = "") -> str:
        """BUG-9 FIX: Run LLM call in a thread with timeout + graceful degradation."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                generate_response, prompt, self.provider, system_prompt
            )
            try:
                return future.result(timeout=self._timeout)
            except concurrent.futures.TimeoutError:
                _log.warning("ThinkingEngine timed out after %ds — returning partial result",
                             self._timeout)
                return (
                    f"[Thinking timed out after {self._timeout}s]\n\n"
                    f"Partial analysis for: {prompt[:200]}\n\n"
                    "Consider breaking your question into smaller parts, or "
                    "use /use-model to switch to a faster provider."
                )
            except Exception as e:
                _log.warning("ThinkingEngine._generate_with_timeout failed: %s", e)
                raise

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
            # BUG-9 FIX: use timeout-protected call instead of bare generate_response
            self.last_trace = self._generate_with_timeout(
                prompt,
                system_prompt="Strategic reasoning engine. Direct. Precise. No fluff.",
            )
            return self.last_trace
        except Exception as e:
            _log.warning("ThinkingEngine.reason failed: %s", e)
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
            # BUG-9 FIX: use timeout-protected call
            result = self._generate_with_timeout(
                prompt,
                system_prompt="Creative lateral thinking engine. Be genuinely surprising."
            )
            self.last_trace = result
            return result
        except Exception:
            return self.reason(query)

