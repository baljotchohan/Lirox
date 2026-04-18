"""Lirox v2.0 Autonomy — Self Improver (AI Refactor Engine)"""

from __future__ import annotations

import ast
import difflib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from lirox.autonomy.code_executor import CodeExecutor
from lirox.autonomy.filesystem_manager import FilesystemManager


_executor = CodeExecutor()
_fs = FilesystemManager()


# ─────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────

@dataclass
class Issue:
    file: str
    line: Optional[int]
    kind: str
    message: str
    severity: str = "medium"


@dataclass
class Patch:
    issue: Issue
    original: str
    patched: str
    diff: str
    applied: bool = False


def make_diff(original: str, patched: str, filename: str) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )


# ─────────────────────────────────────────────────────────────
# Self Improver
# ─────────────────────────────────────────────────────────────

class SelfImprover:
    """Analyse, fix, and improve the codebase autonomously."""

    def __init__(self, root: Optional[str] = None):
        if root is None:
            # Default to the lirox package directory
            root = str(Path(__file__).parent.parent)
        self.root = Path(root)
        self.issues: List[Issue] = []
        self.patches: List[Patch] = []

    # ─────────────────────────────────────────────────────────
    # 🔍 Scan System
    # ─────────────────────────────────────────────────────────

    def scan(self) -> List[Issue]:
        self.issues = []

        for py_file in _fs.get_python_files(str(self.root)):
            ok, source = _fs.read_file(py_file)
            if not ok:
                continue

            # Syntax errors
            for err in _executor.check_syntax(source):
                self.issues.append(Issue(py_file, 0, "syntax", err, "high"))
                continue

            self.issues.extend(self._ast_checks(py_file, source))
            self.issues.extend(self._line_checks(py_file, source))

        return self.issues

    def _ast_checks(self, path: str, source: str) -> List[Issue]:
        issues = []

        try:
            tree = ast.parse(source)
        except:
            return issues

        for node in ast.walk(tree):
            # Bare except
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append(Issue(path, node.lineno, "bare_except",
                    "Use specific exceptions instead of bare except", "medium"))

        return issues

    def _line_checks(self, path: str, source: str) -> List[Issue]:
        issues = []
        for i, line in enumerate(source.splitlines(), 1):
            if re.match(r"^\s*#\s*(TODO|FIXME)", line):
                issues.append(Issue(path, i, "todo", line.strip(), "low"))
            if len(line) > 120:
                issues.append(Issue(path, i, "long_line", "Line too long", "low"))
        return issues

    # ─────────────────────────────────────────────────────────
    # 🤖 Patch Generation (LLM)
    # ─────────────────────────────────────────────────────────

    def generate_patches(self, max_patches: int = 10) -> List[Patch]:
        from lirox.utils.llm import generate_response

        self.patches = []

        for issue in self.issues[:max_patches]:
            path = Path(issue.file)
            if not path.exists():
                continue

            original = path.read_text(errors="replace")

            prompt = f"""
You are fixing a SPECIFIC issue in a Python file. Make the MINIMUM change needed.
Do NOT restructure or simplify the file. Do NOT remove any existing code.
Keep all imports, classes, methods, and docstrings intact.

File: {issue.file}
Issue to fix: {issue.message}
Severity: {issue.severity}

CURRENT CODE (full file — preserve all of it except the specific fix):
{original[:4000]}

OUTPUT: Return the COMPLETE file content with ONLY the specific fix applied.
The output must be at least as long as the input.
"""

            try:
                patched = generate_response(
                    prompt, provider="auto",
                    system_prompt="Fix the code issue. Return only valid Python.",
                )

                # SAFETY: reject if patched is <40% of original — LLM replaced whole file
                if len(patched.strip()) < len(original.strip()) * 0.40:
                    continue  # skip destructive patch

                # SAFETY: reject if patched has fewer than 5 lines — probably truncated
                if patched.count("\n") < 5:
                    continue

                diff = make_diff(original, patched, issue.file)

                if diff:
                    self.patches.append(
                        Patch(issue, original, patched, diff)
                    )
            except Exception:
                pass

        return self.patches

    # ─────────────────────────────────────────────────────────
    # ⚙️ Apply + Rollback
    # ─────────────────────────────────────────────────────────

    def apply_patch(self, patch: Patch) -> bool:
        path = Path(patch.issue.file)

        try:
            shutil.copy2(path, path.with_suffix(".bak"))
            path.write_text(patch.patched)
            patch.applied = True
            return True
        except:
            return False

    def rollback(self) -> int:
        restored = 0
        for bak in self.root.rglob("*.bak"):
            original = bak.with_suffix("")
            shutil.copy2(bak, original)
            bak.unlink()
            restored += 1
        return restored

    # ─────────────────────────────────────────────────────────
    # 📡 Streaming (Agent Mode)
    # ─────────────────────────────────────────────────────────

    def improve_and_stream(self) -> Generator[Dict[str, Any], None, None]:
        yield {"type": "progress", "message": "🔍 Scanning code..."}

        issues = self.scan()

        if not issues:
            yield {"type": "success", "message": "No issues found"}
            return

        yield {"type": "progress", "message": f"Found {len(issues)} issues"}

        patches = self.generate_patches()

        yield {"type": "progress", "message": f"Generated {len(patches)} fixes"}

        for p in patches:
            yield {
                "type": "patch",
                "message": f"{p.issue.file}: {p.issue.message}"
            }
            yield {
                "type": "diff",
                "message": p.diff[:500]
            }

    def analyse_and_stream(self, root: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """Alias for improve_and_stream(); optionally re-targets a different root."""
        if root is not None:
            self.root = Path(root)
        yield from self.improve_and_stream()

    def get_improvement_summary(self, root: Optional[str] = None) -> str:
        """Return a Markdown-formatted summary of issues and patches.

        If *root* is provided, re-targets the scan to that directory first.
        Reuses already-scanned data if available and root hasn't changed.
        """
        if root is not None:
            new_root = Path(root)
            if new_root != self.root:
                self.root = new_root
                self.issues = []
                self.patches = []

        if not self.issues:
            self.scan()
        if not self.patches and self.issues:
            self.generate_patches()

        issues = self.issues
        patches = self.patches

        lines: List[str] = [
            "## 🔬 Self-Improvement Summary\n",
            f"**Root scanned:** `{self.root}`",
            f"**Issues found:** {len(issues)}",
            f"**Patches generated:** {len(patches)}\n",
        ]

        if issues:
            lines.append("### Issues")
            by_severity: Dict[str, List[Issue]] = {}
            for iss in issues:
                by_severity.setdefault(iss.severity, []).append(iss)
            for sev in ("high", "medium", "low"):
                group = by_severity.get(sev, [])
                if group:
                    lines.append(f"\n#### {sev.capitalize()} ({len(group)})")
                    for iss in group[:5]:
                        loc = f":{iss.line}" if iss.line else ""
                        lines.append(f"- `{iss.file}{loc}` — {iss.message}")
                    if len(group) > 5:
                        lines.append(f"- …and {len(group) - 5} more")

        if patches:
            lines.append("\n### Generated Patches")
            for p in patches:
                lines.append(f"- **{p.issue.file}**: {p.issue.message}")

        if not issues:
            lines.append("\n✅ No issues found — codebase looks clean!")

        return "\n".join(lines)