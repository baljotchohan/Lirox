"""Lirox Autonomy — Code Tester.

Generates unit tests for supplied Python source and runs them, reporting
pass/fail counts and any failure messages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from lirox.autonomy.code_executor import CodeExecutor, ExecutionResult


@dataclass
class TestReport:
    passed:   int = 0
    failed:   int = 0
    errors:   List[str] = field(default_factory=list)
    output:   str = ""

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and not self.errors

    def summary(self) -> str:
        status = "✓ All tests passed" if self.all_passed else "✖ Some tests failed"
        return (
            f"{status}  (passed={self.passed}, failed={self.failed})\n"
            + (("\n".join(self.errors)) if self.errors else "")
        )


class CodeTester:
    """Generate and run tests for a piece of Python source code."""

    def __init__(self, executor: CodeExecutor = None) -> None:
        self._executor = executor or CodeExecutor()

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_tests(self, source: str, description: str = "") -> str:
        """Ask the LLM to write unittest tests for *source*."""
        from lirox.utils.llm import generate_response

        prompt = (
            "Write Python `unittest` tests for the following code.\n"
            "Rules:\n"
            "• Use `unittest.TestCase`.\n"
            "• Test the happy path and at least one edge case.\n"
            "• Call `unittest.main()` at the bottom.\n"
            "• Only output runnable Python — no explanation.\n\n"
        )
        if description:
            prompt += f"Description: {description}\n\n"
        prompt += f"Source:\n```python\n{source[:4000]}\n```\n"

        return generate_response(
            prompt,
            provider="auto",
            system_prompt="Python test writer. Output ONLY executable Python code.",
        )

    def run_tests(self, source: str, test_source: str = "") -> TestReport:
        """Run *test_source* (or auto-generate tests for *source*) and return a report."""
        if not test_source:
            test_source = self.generate_tests(source)

        combined = source + "\n\n" + test_source
        result   = self._executor.execute(combined)
        return self._parse_result(result)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_result(result: ExecutionResult) -> TestReport:
        report = TestReport(output=result.stdout + result.stderr)

        if result.timed_out:
            report.errors.append("Test run timed out.")
            return report

        output = (result.stdout + result.stderr).strip()

        # Parse standard unittest summary line: e.g. "Ran 5 tests in 0.001s"
        import re
        m = re.search(r"Ran (\d+) test", output)
        if m:
            total = int(m.group(1))
            fail_m = re.search(r"FAILED.*failures=(\d+)", output)
            err_m  = re.search(r"FAILED.*errors=(\d+)", output)
            failed = int(fail_m.group(1)) if fail_m else 0
            errored = int(err_m.group(1)) if err_m else 0
            report.failed = failed + errored
            report.passed = total - report.failed
        elif result.success:
            report.passed = 1  # At least ran without crashing
        else:
            report.failed = 1
            report.errors.append(result.stderr or result.error or "Unknown error")

        return report
