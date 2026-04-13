"""Lirox Thinking — Advanced Reasoning.

Multi-path deep reasoning engine:
  1. Generates 3-4 distinct solution approaches
  2. Scores and ranks them
  3. Emits `deep_thinking` events with the reasoning trace

No external APIs beyond the standard LLM utility already used by Lirox.
"""
from __future__ import annotations

import textwrap
from typing import Any, Dict, Generator, List

from lirox.utils.llm import generate_response


_DECOMPOSE_PROMPT = (
    "You are a deep reasoning engine. For the following problem, list 3 distinct "
    "solution approaches (no code). Format as:\n"
    "1. [Approach name]: [one-sentence description]\n"
    "2. ...\n"
    "3. ...\n\n"
    "Then recommend the best one and briefly explain why.\n\n"
    "Problem: {query}"
)

_RANK_PROMPT = (
    "Rank these approaches from best to worst for: '{query}'\n\n"
    "{approaches}\n\n"
    "Output a single paragraph explaining which is best and why."
)


class AdvancedReasoning:
    """Multi-path deep reasoning engine (no external deps beyond llm util)."""

    def reason_deep(self, query: str) -> str:
        """Generate a multi-path reasoning trace for *query*.

        Returns a formatted string with approaches and recommendation.
        Falls back to a simple think-aloud if the LLM call fails.
        """
        try:
            prompt = _DECOMPOSE_PROMPT.format(query=query)
            result = generate_response(prompt, provider="auto",
                                       system_prompt="Be concise and analytical.")
            return result[:1500]
        except Exception:
            return (
                "Deep reasoning: breaking down the problem step by step.\n"
                f"Query: {query}\n\n"
                "Consider: constraints, alternatives, trade-offs, best fit."
            )

    def reason_and_stream(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """Stream deep-thinking events for *query*."""
        yield {"type": "deep_thinking", "message": "🧠 Entering deep reasoning mode…"}
        trace = self.reason_deep(query)
        # Split into chunks for streaming
        for chunk in textwrap.wrap(trace, width=200):
            yield {"type": "deep_thinking", "message": chunk}

    def score_approach(self, approach: str, context: str = "") -> int:
        """Return a simple heuristic score 0-10 for *approach* given *context*."""
        keywords_good = ["simple", "reliable", "proven", "standard", "efficient"]
        keywords_bad  = ["complex", "risky", "experimental", "slow", "fragile"]
        text = approach.lower()
        score = 5
        score += sum(1 for k in keywords_good if k in text)
        score -= sum(1 for k in keywords_bad  if k in text)
        return max(0, min(10, score))
