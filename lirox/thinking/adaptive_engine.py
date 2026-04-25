"""
Adaptive Thinking Engine
Replaces the broken real_engine.py with a clean, depth-adaptive reasoner.

Complexity levels:
  low    → skip (caller handles)
  medium → single-pass analysis
  high   → multi-perspective deliberation
"""
import logging
import time
from typing import Any, Dict, Generator

from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.thinking.adaptive")


class AdaptiveThinkingEngine:
    """
    Adaptive reasoning engine.

    Yields dicts with keys:
      type    → "thinking_step" | "done"
      message → human-readable status
      data    → payload (on "done": the ThinkingResult dict)
    """

    def think(
        self,
        query: str,
        context: Dict[str, Any],
        complexity: str = "medium",
    ) -> Generator[Dict, None, None]:
        """
        Run thinking and yield progress events.

        Final event: {"type": "done", "data": {...}}
        """
        start = time.time()

        if complexity == "high":
            yield from self._deep_think(query, context, start)
        else:
            yield from self._medium_think(query, context, start)

    # ── Medium complexity: single-pass analysis ──────────────────────────────

    def _medium_think(self, query, context, start):
        yield {"type": "thinking_step", "message": "🔍 Analysing task requirements..."}

        prompt = (
            f"Task: {query}\n\n"
            "Briefly analyse:\n"
            "1. What is the user's core goal?\n"
            "2. What approach will produce the best result?\n"
            "3. What are the 2-3 most important considerations?\n\n"
            "Be concise. 3-4 sentences total."
        )
        analysis = generate_response(
            prompt, provider="auto",
            system_prompt="You are a task analyst. Be brief and direct.",
        )

        elapsed = time.time() - start
        yield {
            "type": "done",
            "message": "✓ Analysis complete",
            "data": {
                "decision": query,
                "reasoning": analysis,
                "approach": "direct",
                "confidence": 80,
                "elapsed": elapsed,
            },
        }

    # ── High complexity: multi-perspective deliberation ──────────────────────

    def _deep_think(self, query, context, start):
        yield {"type": "thinking_step", "message": "🧠 Starting deep multi-perspective analysis..."}

        # Perspective 1: Requirements
        yield {"type": "thinking_step", "message": "📋 Extracting requirements..."}
        reqs = generate_response(
            f"List the concrete requirements for: {query}\n"
            "Be specific. 5 bullet points max.",
            provider="auto",
            system_prompt="Requirements analyst. Bullet points only.",
        )

        # Perspective 2: Approach
        yield {"type": "thinking_step", "message": "🎯 Evaluating approach..."}
        approach = generate_response(
            f"Best approach to accomplish: {query}\n\n"
            f"Context: {str(context)[:300]}\n\n"
            "Consider: scope, quality, efficiency. 3-4 sentences.",
            provider="auto",
            system_prompt="Senior architect. Direct and opinionated.",
        )

        # Perspective 3: Risk check
        yield {"type": "thinking_step", "message": "⚠️ Checking edge cases..."}
        risks = generate_response(
            f"What could go wrong when: {query}\n"
            "List up to 3 risks and how to avoid them.",
            provider="auto",
            system_prompt="Risk analyst. Be concise.",
        )

        # Synthesis
        yield {"type": "thinking_step", "message": "✨ Synthesising decision..."}
        decision = generate_response(
            f"Given this task: {query}\n\n"
            f"Requirements: {reqs[:300]}\n"
            f"Best approach: {approach[:300]}\n"
            f"Risks to avoid: {risks[:200]}\n\n"
            "What is the final recommended execution plan in 2-3 sentences?",
            provider="auto",
            system_prompt="Senior decision maker. Output the plan only.",
        )

        elapsed = time.time() - start
        yield {
            "type": "done",
            "message": "✓ Deep analysis complete",
            "data": {
                "decision": decision,
                "reasoning": approach,
                "requirements": reqs,
                "risks": risks,
                "approach": "deliberate",
                "confidence": 90,
                "elapsed": elapsed,
            },
        }
