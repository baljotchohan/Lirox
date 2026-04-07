"""
Lirox v0.5 — Self-Improvement Engine

When /improve is called or an error is detected:
1. Audits its own code files for known issues
2. Uses LLM to generate patches
3. Writes the patches to disk
4. Reports what was changed

Also handles auto-fix on skill/agent errors.
"""
from __future__ import annotations

import ast
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any

from lirox.utils.llm import generate_response
from lirox.config import PROJECT_ROOT


_AUDIT_PROMPT = """
Audit this Python code file for:
1. Potential bugs or runtime errors
2. Missing error handling (bare except, no try/catch)
3. Performance issues (N+1 queries, blocking I/O in loops)
4. Security issues (injection risks, hardcoded secrets, unsafe eval)
5. Dead code or unused imports

FILE: {filename}

CODE:
{code}

Output a JSON array of issues found:
[
  {{
    "line": 42,
    "severity": "high|medium|low",
    "issue": "description of the problem",
    "suggestion": "how to fix it"
  }}
]

If no issues found, output: []
"""

_PATCH_PROMPT = """
Apply this fix to the Python code:

ISSUE: {issue}
SUGGESTION: {suggestion}

CURRENT CODE:
{code}

Output ONLY the corrected Python code (no markdown, no explanation).
The fix should be minimal — change only what's needed to address the issue.
"""

_SELF_IMPROVE_PROMPT = """
You are analyzing a personal AI agent's codebase for self-improvement opportunities.

Review these files and identify the 3 highest-impact improvements that would:
1. Make the agent more helpful or capable
2. Fix actual bugs or error conditions
3. Improve learning / memory retention

FILES REVIEWED:
{files_summary}

RECENT ERRORS (if any):
{errors}

Output a JSON array of improvements:
[
  {{
    "file": "relative/path/to/file.py",
    "description": "what to improve",
    "impact": "high|medium",
    "effort": "low|medium|high"
  }}
]
"""


class SelfImprover:
    """
    Analyzes and patches the agent's own code files.
    """

    # Files the improver is allowed to patch
    PATCHABLE_FILES = [
        "lirox/mind/agent.py",
        "lirox/mind/trainer.py",
        "lirox/mind/learnings.py",
        "lirox/mind/skills/registry.py",
        "lirox/mind/sub_agents/registry.py",
        "lirox/agents/personal_agent.py",
    ]

    def __init__(self):
        self._root = Path(PROJECT_ROOT)
        self._error_log: List[Dict] = []

    def log_error(self, source: str, error: str) -> None:
        """Log a runtime error for the next improvement cycle."""
        self._error_log.append({
            "source": source,
            "error": error,
            "at": time.time(),
        })
        # Keep last 20 errors
        if len(self._error_log) > 20:
            self._error_log = self._error_log[-20:]

    def audit_file(self, relative_path: str) -> List[Dict]:
        """Audit a single file for issues."""
        full_path = self._root / relative_path
        if not full_path.exists():
            return []

        code = full_path.read_text()

        # Quick static checks first
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as se:
            issues.append({
                "line": se.lineno,
                "severity": "high",
                "issue": f"Syntax error: {se.msg}",
                "suggestion": "Fix the syntax error at the indicated line",
            })
            return issues  # Can't proceed if syntax is broken

        # LLM audit
        try:
            raw = generate_response(
                _AUDIT_PROMPT.format(filename=relative_path, code=code[:8000]),
                provider="auto",
                system_prompt="You are a Python code auditor. Output only JSON.",
            )
            import json
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                llm_issues = json.loads(m.group())
                if isinstance(llm_issues, list):
                    issues.extend(llm_issues)
        except Exception:
            pass

        return issues

    def improve(self) -> Dict[str, Any]:
        """
        Run a full self-improvement cycle.
        Returns summary of what was found and fixed.
        """
        results = {
            "files_audited": 0,
            "issues_found": 0,
            "patches_applied": 0,
            "improvements": [],
        }

        for rel_path in self.PATCHABLE_FILES:
            full_path = self._root / rel_path
            if not full_path.exists():
                continue

            results["files_audited"] += 1
            issues = self.audit_file(rel_path)

            high_issues = [i for i in issues if i.get("severity") == "high"]
            results["issues_found"] += len(issues)

            for issue in high_issues[:2]:  # Max 2 auto-patches per file
                try:
                    code = full_path.read_text()
                    patched = generate_response(
                        _PATCH_PROMPT.format(
                            issue=issue["issue"],
                            suggestion=issue["suggestion"],
                            code=code[:8000],
                        ),
                        provider="auto",
                        system_prompt="Apply the fix. Output ONLY corrected Python code.",
                    )
                    patched = patched.strip().lstrip("```python").lstrip("```").rstrip("```").strip()

                    # Validate it compiles
                    compile(patched, rel_path, "exec")

                    # Backup + write
                    backup = full_path.with_suffix(".py.bak")
                    backup.write_text(code)
                    full_path.write_text(patched)

                    results["patches_applied"] += 1
                    results["improvements"].append({
                        "file": rel_path,
                        "fix": issue["issue"],
                    })
                except Exception as e:
                    results["improvements"].append({
                        "file": rel_path,
                        "error": f"Could not auto-patch: {e}",
                    })

        return results

    def suggest_improvements(self) -> str:
        """
        Ask LLM for high-level improvement suggestions.
        Returns formatted text for display.
        """
        files_summary = []
        for rel_path in self.PATCHABLE_FILES:
            full_path = self._root / rel_path
            if full_path.exists():
                lines = len(full_path.read_text().split("\n"))
                files_summary.append(f"  {rel_path} ({lines} lines)")

        errors_text = "\n".join(
            f"  [{e['source']}] {e['error'][:100]}"
            for e in self._error_log[-5:]
        ) or "  None logged"

        try:
            raw = generate_response(
                _SELF_IMPROVE_PROMPT.format(
                    files_summary="\n".join(files_summary),
                    errors=errors_text,
                ),
                provider="auto",
                system_prompt="You suggest code improvements. Output JSON.",
            )
            import json
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                suggestions = json.loads(m.group())
                lines = ["IMPROVEMENT SUGGESTIONS:\n"]
                for i, s in enumerate(suggestions[:5], 1):
                    lines.append(
                        f"  [{s.get('impact','?').upper()}] {s.get('description','')}\n"
                        f"    File: {s.get('file','?')} | Effort: {s.get('effort','?')}\n"
                    )
                return "\n".join(lines)
        except Exception as e:
            pass
        return "Could not generate suggestions. Check LLM connection."
