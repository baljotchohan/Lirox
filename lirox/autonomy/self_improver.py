"""Lirox Autonomy — Self-Improver

Scans the Lirox codebase for potential issues, generates improvement
suggestions, and applies patches after user confirmation.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, Generator, List

from lirox.autonomy.code_executor import CodeExecutor
from lirox.autonomy.filesystem_manager import FilesystemManager


_executor = CodeExecutor()
_fs = FilesystemManager()


class SelfImprover:
    """Analyse the Lirox source tree and propose targeted improvements."""

    # ------------------------------------------------------------------
    # Codebase scanning
    # ------------------------------------------------------------------

    def scan_codebase(self, root: str) -> List[Dict[str, Any]]:
        """Return a list of issue dicts found across all Python files under *root*.

        Each issue has keys: ``file``, ``line``, ``kind``, ``message``.
        """
        issues: List[Dict[str, Any]] = []
        for py_path in _fs.get_python_files(root):
            ok, source = _fs.read_file(py_path)
            if not ok:
                continue
            issues.extend(self._lint_source(py_path, source))
        return issues

    def _lint_source(self, path: str, source: str) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []

        # Syntax check
        for err in _executor.check_syntax(source):
            issues.append({"file": path, "line": 0, "kind": "syntax", "message": err})
            return issues  # syntax errors make AST analysis meaningless

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return issues

        lines = source.splitlines()

        for node in ast.walk(tree):
            # Bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append({
                    "file": path,
                    "line": node.lineno,
                    "kind": "bare_except",
                    "message": "Bare 'except:' clause — catch specific exceptions instead.",
                })

        # Line-level checks
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.match(r"^\s*#\s*(TODO|FIXME|HACK|XXX)", line, re.IGNORECASE):
                issues.append({
                    "file": path,
                    "line": i,
                    "kind": "todo_comment",
                    "message": f"Unresolved comment: {stripped[:80]}",
                })
            if len(line) > 120:
                issues.append({
                    "file": path,
                    "line": i,
                    "kind": "long_line",
                    "message": f"Line length {len(line)} > 120 chars.",
                })

        return issues

    # ------------------------------------------------------------------
    # Streaming interface for the agent bus
    # ------------------------------------------------------------------

    def analyse_and_stream(
        self, root: str
    ) -> Generator[Dict[str, Any], None, None]:
        """Scan *root* and stream progress events for each file and finding."""
        yield {"type": "agent_progress", "message": "🔍 Scanning codebase for issues…"}

        py_files = _fs.get_python_files(root)
        yield {
            "type": "agent_progress",
            "message": f"  Found {len(py_files)} Python files to analyse.",
        }

        all_issues: List[Dict[str, Any]] = []
        for py_path in py_files:
            ok, source = _fs.read_file(py_path)
            if not ok:
                continue
            file_issues = self._lint_source(py_path, source)
            if file_issues:
                all_issues.extend(file_issues)

        if not all_issues:
            yield {"type": "tool_result", "message": "✓ No issues found — codebase looks clean!"}
            return

        yield {
            "type": "tool_result",
            "message": f"Found {len(all_issues)} potential issue(s):",
        }
        for issue in all_issues[:20]:  # cap output
            rel = Path(issue["file"]).name
            yield {
                "type": "tool_result",
                "message": f"  [{issue['kind']}] {rel}:{issue['line']} — {issue['message']}",
            }
        if len(all_issues) > 20:
            yield {
                "type": "tool_result",
                "message": f"  … and {len(all_issues) - 20} more issue(s).",
            }

    def get_improvement_summary(self, root: str) -> str:
        """Return a human-readable markdown summary of codebase issues."""
        issues = self.scan_codebase(root)
        if not issues:
            return "✅ Codebase scan complete — no issues found."

        lines = [f"## Codebase Analysis — {len(issues)} issue(s) found\n"]
        for issue in issues[:30]:
            rel = Path(issue["file"]).name
            lines.append(
                f"- **{issue['kind']}** `{rel}:{issue['line']}` — {issue['message']}"
            )
        if len(issues) > 30:
            lines.append(f"\n_…and {len(issues) - 30} more._")
        return "\n".join(lines)
