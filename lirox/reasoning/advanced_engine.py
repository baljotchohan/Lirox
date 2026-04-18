"""Lirox V1 — Advanced 8-Phase Reasoning Engine.

Implements the full reasoning pipeline:
  UNDERSTAND → DECOMPOSE → ANALYZE → EVALUATE → SIMULATE → REFINE → PLAN → VERIFY

Each phase builds on the previous, producing a rich structured reasoning trace
that the agent can use to give higher-quality answers.

Usage:
    from lirox.reasoning.advanced_engine import AdvancedReasoningEngine

    engine = AdvancedReasoningEngine()
    result = engine.reason("How do I scale a FastAPI app to 10k users?")
    print(result.summary)        # concise recommendation
    print(result.full_trace)     # all 8 phases
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from lirox.utils.llm import generate_response


# ── Phase definitions ────────────────────────────────────────────────────────

_PHASES = [
    ("UNDERSTAND",  "What is really being asked? What are the unstated needs or goals? "
                    "What context is critical?"),
    ("DECOMPOSE",   "Break this into 3-5 sub-problems or distinct components. "
                    "What sub-problems must be solved?"),
    ("ANALYZE",     "For each component, what are the key constraints, trade-offs, "
                    "and dependencies? What information is known vs. unknown?"),
    ("EVALUATE",    "What are the 2-3 best solution approaches? Score each on: "
                    "simplicity (1-10), reliability (1-10), speed (1-10)."),
    ("SIMULATE",    "Walk through the top approach step-by-step. What could go wrong "
                    "at each step? What edge cases exist?"),
    ("REFINE",      "Given the simulation, what adjustments improve the approach? "
                    "What pre-conditions or guard-rails are needed?"),
    ("PLAN",        "Create a concrete, ordered action plan. Each step should be "
                    "specific and actionable."),
    ("VERIFY",      "Does the plan fully address the original question? "
                    "What would indicate success? What risks remain?"),
]

_COMBINED_PROMPT = """\
You are an expert reasoning engine. Analyze the following query through 8 structured phases.
Be concise (2-3 sentences per phase). Output EXACTLY this structure:

UNDERSTAND: ...
DECOMPOSE: ...
ANALYZE: ...
EVALUATE: ...
SIMULATE: ...
REFINE: ...
PLAN: ...
VERIFY: ...

Query: {query}
{context_block}"""


@dataclass
class ReasoningResult:
    query:      str
    phases:     Dict[str, str]    = field(default_factory=dict)
    summary:    str               = ""
    full_trace: str               = ""
    error:      Optional[str]     = None

    def to_context_string(self, max_chars: int = 3000) -> str:
        """Format phases as a compact reasoning context for downstream LLM calls."""
        lines = [f"[REASONING for: {self.query[:100]}]"]
        for phase, content in self.phases.items():
            lines.append(f"{phase}: {content}")
        return "\n".join(lines)[:max_chars]


# ── Engine ───────────────────────────────────────────────────────────────────

class AdvancedReasoningEngine:
    """8-phase structured reasoning engine (single combined LLM call for speed)."""

    def __init__(self, provider: str = "auto"):
        self.provider = provider

    # ── Public API ────────────────────────────────────────────────────────

    def reason(self, query: str, context: str = "") -> ReasoningResult:
        """Run all 8 reasoning phases and return a structured result.

        Falls back gracefully if the LLM call fails.
        """
        result = ReasoningResult(query=query)

        context_block = f"\nContext:\n{context[:1500]}" if context else ""
        prompt = _COMBINED_PROMPT.format(
            query=query,
            context_block=context_block,
        )

        try:
            raw = generate_response(
                prompt,
                provider=self.provider,
                system_prompt=(
                    "You are a structured reasoning engine. Output exactly the 8 phases "
                    "requested. Be concise and specific. No extra commentary."
                ),
            )
            result.phases    = self._parse_phases(raw)
            result.full_trace = raw
            result.summary   = self._build_summary(result.phases, query)
        except Exception as e:
            result.error     = str(e)
            result.phases    = self._fallback_phases(query)
            result.full_trace = self._format_phases(result.phases)
            result.summary   = result.phases.get("PLAN", "")

        return result

    def reason_stream(
        self, query: str, context: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream reasoning phase-by-phase, yielding events for the UI."""
        yield {"type": "deep_thinking", "message": "🧠 Starting 8-phase reasoning…"}

        result = self.reason(query, context)

        for phase_name in ["UNDERSTAND", "DECOMPOSE", "ANALYZE", "EVALUATE",
                           "SIMULATE", "REFINE", "PLAN", "VERIFY"]:
            content = result.phases.get(phase_name, "")
            if content:
                yield {
                    "type":    "deep_thinking",
                    "message": f"[{phase_name}] {content[:300]}",
                }

        yield {
            "type":   "deep_thinking",
            "message": f"✓ Reasoning complete: {result.summary[:200]}",
        }
        yield {"type": "reasoning_done", "result": result}

    # ── Parsing helpers ───────────────────────────────────────────────────

    def _parse_phases(self, raw: str) -> Dict[str, str]:
        """Parse the LLM output into phase → content dict."""
        phases: Dict[str, str] = {}
        phase_names = [p[0] for p in _PHASES]

        current_phase: Optional[str] = None
        current_lines: List[str]     = []

        for line in raw.splitlines():
            matched = False
            for name in phase_names:
                if line.upper().startswith(f"{name}:"):
                    if current_phase:
                        phases[current_phase] = " ".join(current_lines).strip()
                    current_phase = name
                    content = line[len(name) + 1:].strip()
                    current_lines = [content] if content else []
                    matched = True
                    break
            if not matched and current_phase:
                stripped = line.strip()
                if stripped:
                    current_lines.append(stripped)

        if current_phase and current_lines:
            phases[current_phase] = " ".join(current_lines).strip()

        # Fill any missing phases with empty string
        for name in phase_names:
            phases.setdefault(name, "")

        return phases

    def _build_summary(self, phases: Dict[str, str], query: str) -> str:
        """Extract the most actionable summary from PLAN + VERIFY phases."""
        plan   = phases.get("PLAN", "")
        verify = phases.get("VERIFY", "")
        if plan:
            return plan[:400]
        if verify:
            return verify[:400]
        return f"Reasoning complete for: {query[:100]}"

    def _format_phases(self, phases: Dict[str, str]) -> str:
        lines = []
        for name, content in phases.items():
            if content:
                lines.append(f"{name}: {content}")
        return "\n".join(lines)

    def _fallback_phases(self, query: str) -> Dict[str, str]:
        return {
            "UNDERSTAND": f"Query asks: {query[:150]}",
            "DECOMPOSE":  "Breaking into components: problem definition, constraints, approach.",
            "ANALYZE":    "Key factors: feasibility, complexity, dependencies.",
            "EVALUATE":   "Approaches: direct solution, iterative refinement, alternative path.",
            "SIMULATE":   "Checking steps: identify blockers, validate assumptions.",
            "REFINE":     "Adjustment: add error handling and edge-case coverage.",
            "PLAN":       "1. Define scope  2. Implement core  3. Test  4. Refine",
            "VERIFY":     "Success: query is fully addressed with no open blockers.",
        }
