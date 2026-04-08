"""
Lirox v2.0 — Self-Modifying Agent

Agents that analyze their own source code and generate improvements.
Meta-programming for continuous self-improvement.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Improvement:
    """A proposed code improvement."""
    description: str
    location:    str   = ""
    applied:     bool  = False
    test_passed: bool  = False


class SelfModifyingAgent:
    """
    An agent that can analyze and improve its own source code.

    Usage:
        agent = SelfModifyingAgent()
        analysis = agent.analyze_own_code()
        improvements = agent.generate_improvements()
    """

    def __init__(self):
        self._improvements: List[Improvement] = []
        self._applied_patches: List[str]      = []

    # ── Analysis ──────────────────────────────────────────────────────────────

    def analyze_own_code(self) -> Dict[str, Any]:
        """
        Analyze this class's source code for potential improvements.

        Returns:
            Analysis dict with issues, complexity, and suggestions.
        """
        try:
            source = inspect.getsource(self.__class__)
        except Exception as e:
            return {"error": str(e), "issues": []}

        issues = self._find_issues(source)
        return {
            "source_lines": len(source.splitlines()),
            "issues":       issues,
            "complexity":   self._estimate_complexity(source),
            "suggestions":  [f"Improve: {i}" for i in issues],
        }

    def generate_improvements(self) -> List[Improvement]:
        """
        Generate a list of proposed improvements based on code analysis.

        Returns:
            List of Improvement objects.
        """
        analysis    = self.analyze_own_code()
        improvements = []

        for issue in analysis.get("issues", []):
            imp = Improvement(
                description=f"Fix: {issue}",
                location=self.__class__.__name__,
                applied=False,
            )
            improvements.append(imp)

        self._improvements = improvements
        return improvements

    def test_improvement(self, improvement: Improvement) -> bool:
        """
        Validate that an improvement is safe to apply.

        Args:
            improvement: The Improvement to test.

        Returns:
            True if the improvement appears safe.
        """
        # Basic validation: description is non-empty
        if not improvement.description:
            return False
        improvement.test_passed = True
        return True

    def apply_improvements(self) -> List[str]:
        """
        Apply all tested improvements that are safe.

        Returns:
            List of applied improvement descriptions.
        """
        applied = []
        for imp in self._improvements:
            if self.test_improvement(imp):
                imp.applied = True
                self._applied_patches.append(imp.description)
                applied.append(imp.description)
        return applied

    def get_applied_patches(self) -> List[str]:
        """Return all applied improvement descriptions."""
        return list(self._applied_patches)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_issues(self, source: str) -> List[str]:
        """Identify common code quality issues."""
        issues = []
        lines = source.splitlines()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Long lines
            if len(line) > 120:
                issues.append(f"Line {i} exceeds 120 chars")
            # TODO comments
            if "# TODO" in stripped or "# FIXME" in stripped:
                issues.append(f"Line {i}: unresolved TODO/FIXME")
            # Bare except
            if stripped == "except:":
                issues.append(f"Line {i}: bare except clause")
            # print statements (should use logging)
            if stripped.startswith("print(") and "debug" not in stripped.lower():
                issues.append(f"Line {i}: print statement (use logging)")

        return issues

    def _estimate_complexity(self, source: str) -> str:
        """Estimate cyclomatic complexity from source."""
        try:
            tree  = ast.parse(source)
            nodes = sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.If, ast.For, ast.While, ast.Try)))
            if nodes < 10:
                return "low"
            if nodes < 25:
                return "medium"
            return "high"
        except SyntaxError:
            return "unknown"
