"""Lirox Thinking — Advanced Reasoning Engine.

When the standard one-shot ThinkingEngine is insufficient, AdvancedReasoning
breaks the problem into multiple reasoning paths, evaluates them, and
proposes a ranked list of solutions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from lirox.utils.llm import generate_response


@dataclass
class ReasoningPath:
    """One candidate approach to a problem."""
    title:       str
    description: str = ""
    steps:       List[str] = field(default_factory=list)
    pros:        List[str] = field(default_factory=list)
    cons:        List[str] = field(default_factory=list)
    score:       float = 0.0   # 0.0 – 1.0 (higher = better fit)


@dataclass
class DeepThinkingResult:
    query:    str
    paths:    List[ReasoningPath] = field(default_factory=list)
    best:     int = 0   # index of recommended path
    summary:  str = ""

    def format(self) -> str:
        lines = [f"🧠 Deep Thinking — {self.query}\n"]
        lines.append(f"Found {len(self.paths)} approach(es):\n")
        for i, p in enumerate(self.paths):
            marker = "★ RECOMMENDED" if i == self.best else f"  Option {i + 1}"
            lines.append(f"  {marker}: {p.title}")
            lines.append(f"    {p.description}")
            if p.pros:
                lines.append("    ✓ " + "; ".join(p.pros))
            if p.cons:
                lines.append("    ✗ " + "; ".join(p.cons))
        if self.summary:
            lines.append(f"\nConclusion: {self.summary}")
        return "\n".join(lines)


class AdvancedReasoning:
    """Multi-path deep reasoning engine."""

    def __init__(self, provider: str = "auto") -> None:
        self.provider = provider

    # ── Public API ─────────────────────────────────────────────────────────

    def think_deep(self, query: str, context: str = "") -> DeepThinkingResult:
        """Run deep multi-path reasoning and return a structured result."""
        raw = self._call_llm(query, context)
        return self._parse(query, raw)

    def reason_with_fallback(self, query: str, context: str = "") -> str:
        """Return a plain-text deep reasoning trace (safe fallback)."""
        try:
            result = self.think_deep(query, context)
            return result.format()
        except Exception:
            return self._minimal_trace(query)

    # ── LLM call ──────────────────────────────────────────────────────────

    def _call_llm(self, query: str, context: str) -> str:
        prompt = (
            "Perform deep, multi-path reasoning for this problem.\n\n"
            f"Problem: {query}\n"
        )
        if context:
            prompt += f"\nContext:\n{context[:2000]}\n"
        prompt += (
            "\nGenerate 3-4 distinct solution approaches. For each approach:\n"
            "  - Title (one line)\n"
            "  - Description (2-3 sentences)\n"
            "  - Pros (comma-separated)\n"
            "  - Cons (comma-separated)\n"
            "  - Steps (numbered, 3-5 items)\n"
            "  - Score (0.0-1.0 confidence)\n\n"
            "End with: RECOMMENDATION: <title of best approach>\n"
            "And: CONCLUSION: <one sentence summary>\n"
        )
        return generate_response(
            prompt,
            self.provider,
            system_prompt=(
                "You are an expert strategic reasoning engine. "
                "Provide structured multi-path analysis."
            ),
        )

    # ── Parsing ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse(query: str, raw: str) -> DeepThinkingResult:
        import re

        result = DeepThinkingResult(query=query)

        # Extract conclusion
        m = re.search(r"CONCLUSION:\s*(.+)", raw, re.IGNORECASE)
        if m:
            result.summary = m.group(1).strip()

        # Extract recommended title
        recommended_title = ""
        rm = re.search(r"RECOMMENDATION:\s*(.+)", raw, re.IGNORECASE)
        if rm:
            recommended_title = rm.group(1).strip()

        # Split into approach blocks (heuristic: numbered or titled paragraphs)
        blocks = re.split(r"\n(?=\d+\.|#+\s|Title:)", raw)
        for block in blocks:
            block = block.strip()
            if len(block) < 20:
                continue

            lines = block.splitlines()
            title_line = lines[0].lstrip("0123456789. #").strip()
            if not title_line or "RECOMMENDATION" in title_line.upper():
                continue

            path = ReasoningPath(title=title_line)

            # Extract fields
            desc_m = re.search(r"Description:\s*(.+?)(?=\n[A-Z]|\Z)", block,
                                re.IGNORECASE | re.DOTALL)
            if desc_m:
                path.description = desc_m.group(1).strip()

            pros_m = re.search(r"Pros?:\s*(.+?)(?=\n[A-Z]|\Z)", block,
                                re.IGNORECASE | re.DOTALL)
            if pros_m:
                path.pros = [p.strip() for p in pros_m.group(1).split(",") if p.strip()]

            cons_m = re.search(r"Cons?:\s*(.+?)(?=\n[A-Z]|\Z)", block,
                                re.IGNORECASE | re.DOTALL)
            if cons_m:
                path.cons = [c.strip() for c in cons_m.group(1).split(",") if c.strip()]

            score_m = re.search(r"Score:\s*([\d.]+)", block, re.IGNORECASE)
            if score_m:
                try:
                    path.score = float(score_m.group(1))
                except ValueError:
                    pass

            result.paths.append(path)

        # Pick best by score or by recommendation title
        if result.paths:
            if recommended_title:
                for i, p in enumerate(result.paths):
                    if recommended_title.lower() in p.title.lower():
                        result.best = i
                        break
            else:
                result.best = max(range(len(result.paths)),
                                  key=lambda i: result.paths[i].score)

        # Fallback: if parsing produced nothing useful, keep raw text
        if not result.paths:
            result.summary = raw[:500]

        return result

    # ── Fallback ───────────────────────────────────────────────────────────

    @staticmethod
    def _minimal_trace(query: str) -> str:
        return f"UNDERSTAND: {query}\nSTRATEGIZE: Apply best available approach.\nPLAN: 1. Analyse 2. Implement 3. Verify"
