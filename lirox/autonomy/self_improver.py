"""Lirox Autonomy — Self Improver.

Scans the project codebase with AST + LLM, detects issues (dead code,
missing error handling, type-safety gaps, etc.), generates patches,
and offers diff-based review with rollback capability.
"""
from __future__ import annotations

import ast
import difflib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


@dataclass
class Issue:
    """A detected code quality issue."""
    file:        str
    line:        Optional[int]
    kind:        str    # "dead_code" | "no_error_handling" | "type_safety" | "style"
    description: str
    severity:    str = "medium"   # "low" | "medium" | "high"


@dataclass
class Patch:
    """A proposed fix for one issue."""
    issue:        Issue
    original:     str     # original file content
    patched:      str     # improved file content
    diff:         str     # unified diff
    applied:      bool = False


def _make_diff(original: str, patched: str, filename: str) -> str:
    orig_lines    = original.splitlines(keepends=True)
    patched_lines = patched.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            orig_lines,
            patched_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )


class SelfImprover:
    """Audit the project codebase and generate improvement patches."""

    def __init__(self, project_root: Optional[str] = None) -> None:
        if project_root is None:
            from lirox.config import PROJECT_ROOT
            project_root = PROJECT_ROOT
        self.root    = Path(project_root)
        self._issues: List[Issue]  = []
        self._patches: List[Patch] = []

    # ── Scan ───────────────────────────────────────────────────────────────

    def scan(self, subdir: str = "lirox") -> List[Issue]:
        """Run static analysis and return all detected issues."""
        from lirox.autonomy.code_intelligence import CodeIntelligence
        ci = CodeIntelligence(str(self.root))
        project = ci.analyse_project(subdir)
        self._issues = []
        for rel, info in project["modules"].items():
            if info["parse_error"]:
                self._issues.append(Issue(
                    file=rel, line=None,
                    kind="syntax_error",
                    description=info["parse_error"],
                    severity="high",
                ))
                continue
            path = self.root / rel
            try:
                source = path.read_text(errors="replace")
            except OSError:
                continue
            self._issues.extend(self._ast_checks(rel, source))
        return self._issues

    # ── Generate patches ───────────────────────────────────────────────────

    def generate_patches(self, max_patches: int = 10) -> List[Patch]:
        """Ask the LLM to generate a patched version for each issue."""
        from lirox.utils.llm import generate_response

        self._patches = []
        for issue in self._issues[:max_patches]:
            path = self.root / issue.file
            if not path.exists():
                continue
            original = path.read_text(errors="replace")
            prompt   = (
                f"Fix the following issue in this Python file.\n\n"
                f"File: {issue.file}\n"
                f"Issue ({issue.kind}): {issue.description}\n\n"
                f"Original source:\n```python\n{original[:4000]}\n```\n\n"
                "Return ONLY the complete corrected Python source — no explanation, "
                "no markdown fences."
            )
            try:
                patched = generate_response(
                    prompt, provider="auto",
                    system_prompt=(
                        "Expert Python refactoring engineer. "
                        "Return ONLY corrected Python source, no commentary."
                    ),
                )
                # Strip accidental markdown fences
                if patched.startswith("```"):
                    patched = "\n".join(
                        l for l in patched.splitlines()
                        if not l.startswith("```")
                    )
                diff = _make_diff(original, patched, issue.file)
                if diff:
                    self._patches.append(
                        Patch(issue=issue, original=original, patched=patched, diff=diff)
                    )
            except Exception:
                pass
        return self._patches

    # ── Apply ──────────────────────────────────────────────────────────────

    def apply_patch(self, patch: Patch, backup: bool = True) -> bool:
        """Write the patched content to disk (with optional backup)."""
        path = self.root / patch.issue.file
        if not path.exists():
            return False
        if backup:
            bak = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, bak)
        try:
            path.write_text(patch.patched, encoding="utf-8")
            patch.applied = True
            return True
        except OSError:
            return False

    def apply_all(self, backup: bool = True) -> Dict[str, Any]:
        applied = failed = 0
        details = []
        for p in self._patches:
            if self.apply_patch(p, backup=backup):
                applied += 1
                details.append({"file": p.issue.file, "status": "applied"})
            else:
                failed += 1
                details.append({"file": p.issue.file, "status": "failed"})
        return {"applied": applied, "failed": failed, "details": details}

    def rollback(self) -> int:
        """Restore all *.bak files created during apply_patch."""
        restored = 0
        for bak in self.root.rglob("*.py.bak"):
            target = bak.with_suffix("")
            shutil.copy2(bak, target)
            bak.unlink()
            restored += 1
        return restored

    # ── Streaming ──────────────────────────────────────────────────────────

    def scan_events(self, subdir: str = "lirox") -> Generator[Dict[str, Any], None, None]:
        """Yield progress events while scanning."""
        from lirox.autonomy.code_intelligence import CodeIntelligence
        ci      = CodeIntelligence(str(self.root))
        files   = ci.list_python_files(subdir)
        issues  = []
        for p in files:
            rel  = str(p.relative_to(self.root))
            yield {"type": "code_analysis", "message": f"Analysing {rel}…"}
            info = ci.analyse_file(p)
            if info["parse_error"]:
                issues.append(Issue(
                    file=rel, line=None, kind="syntax_error",
                    description=info["parse_error"], severity="high",
                ))
                continue
            try:
                source = p.read_text(errors="replace")
            except OSError:
                continue
            for issue in self._ast_checks(rel, source):
                issues.append(issue)
                yield {
                    "type":    "code_analysis",
                    "message": f"  ⚠ {rel}: [{issue.kind}] {issue.description[:80]}",
                }
        self._issues = issues
        yield {
            "type":    "code_analysis",
            "message": f"Scan complete — {len(issues)} issue(s) found.",
        }

    # ── Static checks ──────────────────────────────────────────────────────

    @staticmethod
    def _ast_checks(filename: str, source: str) -> List[Issue]:
        issues: List[Issue] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            # Missing error handling in try blocks
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if (isinstance(handler.type, ast.Name)
                            and handler.type.id == "Exception"):
                        body = handler.body
                        if all(isinstance(s, ast.Pass) for s in body):
                            issues.append(Issue(
                                file=filename,
                                line=getattr(node, "lineno", None),
                                kind="no_error_handling",
                                description="bare `except Exception: pass` swallows errors silently.",
                                severity="medium",
                            ))

            # Functions missing return type hint
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is None and not node.name.startswith("_"):
                    issues.append(Issue(
                        file=filename,
                        line=node.lineno,
                        kind="type_safety",
                        description=f"Public function `{node.name}` missing return type hint.",
                        severity="low",
                    ))

        return issues
