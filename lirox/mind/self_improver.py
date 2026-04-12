"""
Lirox v1.0.0 — Self-Improvement Engine
Patches staged to data/pending_patches/ — never auto-applied.
User reviews with /pending then commits with /apply.
"""
from __future__ import annotations
import ast
import json
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Any

from lirox.utils.llm import generate_response
from lirox.config import PROJECT_ROOT, PATCHES_DIR

_AUDIT_PROMPT = """Audit this Python file for real bugs.
FILE: {filename}
CODE:
{code}
Output JSON array: [{{"line":42,"severity":"high|medium|low","issue":"problem","suggestion":"fix"}}]
If no issues: []"""

_PATCH_PROMPT = """Apply this fix:
ISSUE: {issue}
SUGGESTION: {suggestion}
CODE:
{code}
Output ONLY corrected Python code. Minimal change. No markdown."""

_SUGGEST_PROMPT = """Analyze AI agent codebase for improvements.
FILES:
{files_summary}
ERRORS:
{errors}
Output JSON: [{{"file":"path","description":"improvement","impact":"high|medium","effort":"low|medium|high","why":"reason"}}]"""

_AUDIT_CHUNK_SIZE = 8000  # BUG-H4 FIX: max chars per audit chunk for large-file support


class SelfImprover:
    PATCHABLE   = ["lirox/mind/agent.py","lirox/mind/trainer.py","lirox/mind/learnings.py",
                   "lirox/mind/skills/registry.py","lirox/mind/sub_agents/registry.py",
                   "lirox/agents/personal_agent.py","lirox/memory/manager.py","lirox/utils/streaming.py"]
    AUDIT_ONLY  = ["lirox/orchestrator/master.py","lirox/config.py","lirox/main.py"]

    def __init__(self):
        self._root        = Path(PROJECT_ROOT)
        self._patches_dir = Path(PATCHES_DIR)
        self._patches_dir.mkdir(parents=True, exist_ok=True)
        self._errors: List[Dict] = []

    def log_error(self, source: str, error: str) -> None:
        self._errors.append({"source": source, "error": error, "at": time.time()})
        if len(self._errors) > 30: self._errors = self._errors[-30:]

    def read_own_code(self, filename: str) -> str:
        p = self._root / filename
        return p.read_text(errors="replace") if p.exists() else f"Not found: {filename}"

    def list_source_files(self) -> List[str]:
        return [str(p.relative_to(self._root))
                for p in sorted((self._root/"lirox").rglob("*.py"))
                if "__pycache__" not in str(p)]

    def audit_file(self, rel: str) -> List[Dict]:
        p = self._root / rel
        if not p.exists(): return []
        code = p.read_text(errors="replace")
        try: ast.parse(code)
        except SyntaxError as se:
            return [{"line":se.lineno,"severity":"high","issue":f"Syntax: {se.msg}","suggestion":"Fix syntax"}]
        # BUG-H4 FIX: audit large files in 8KB chunks to avoid silent truncation
        chunk_size = _AUDIT_CHUNK_SIZE
        if len(code) <= chunk_size:
            return self._audit_chunk(code, rel)
        all_issues = []
        seen_issues: set = set()
        for i in range(0, len(code), chunk_size):
            chunk = code[i:i + chunk_size]
            for iss in self._audit_chunk(chunk, rel):
                key = (iss.get("issue", ""), iss.get("line", 0))
                if key not in seen_issues:
                    seen_issues.add(key)
                    all_issues.append(iss)
        return all_issues

    def _audit_chunk(self, chunk: str, rel: str) -> List[Dict]:
        """Audit a single code chunk and return issues."""
        issues = []
        try:
            raw = generate_response(_AUDIT_PROMPT.format(filename=rel, code=chunk),
                                    provider="auto", system_prompt="Code auditor. Output only JSON.")
            raw = re.sub(r"```json?\s*|```\s*","",raw.strip())
            m   = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                found = json.loads(m.group())
                if isinstance(found, list): issues.extend(found)
        except Exception: pass
        return issues

    def improve(self) -> Dict[str, Any]:
        results = {"files_audited":0,"issues_found":0,"patches_staged":0,
                   "patches_applied":0,"improvements":[]}
        for rel in self.PATCHABLE + self.AUDIT_ONLY:
            p = self._root / rel
            if not p.exists(): continue
            results["files_audited"] += 1
            issues = self.audit_file(rel)
            results["issues_found"] += len(issues)
            if rel in self.AUDIT_ONLY:
                for iss in issues[:3]:
                    results["improvements"].append({"file":rel,"issue":iss.get("issue",""),
                                                    "status":"audit only — manual review"})
                continue
            for iss in [i for i in issues if i.get("severity")=="high"][:2]:
                try:
                    code    = p.read_text(errors="replace")
                    patched = generate_response(
                        _PATCH_PROMPT.format(issue=iss["issue"],
                                             suggestion=iss.get("suggestion",""),code=code[:8000]),
                        provider="auto", system_prompt="Apply fix. Output ONLY Python code.")
                    patched = re.sub(r"^```python\s*|^```\s*","",patched.strip()).rstrip("```").strip()
                    compile(patched, rel, "exec")
                    ts   = int(time.time())
                    safe = rel.replace("/","_").replace(".py","")
                    pf   = self._patches_dir / f"{safe}_{ts}.py"
                    mf   = self._patches_dir / f"{safe}_{ts}.json"
                    pf.write_text(patched)
                    mf.write_text(json.dumps({"original_file":rel,"patch_file":str(pf),
                                              "issue":iss.get("issue",""),
                                              "suggestion":iss.get("suggestion",""),
                                              "staged_at":ts}, indent=2))
                    results["patches_staged"] += 1
                    results["improvements"].append({"file":rel,"issue":iss.get("issue","")[:80],
                                                    "status":"staged — run /apply"})
                except Exception as e:
                    results["improvements"].append({"file":rel,"error":f"Could not patch: {e}"})
        return results

    def apply_pending_patches(self) -> Dict[str, Any]:
        results = {"applied":0,"failed":0,"details":[]}
        for mf in sorted(self._patches_dir.glob("*.json")):
            try:
                meta = json.loads(mf.read_text())
                pf   = Path(meta["patch_file"])
                orig = self._root / meta["original_file"]
                if not pf.exists(): continue
                patched = pf.read_text()
                compile(patched, meta["original_file"], "exec")
                shutil.copy2(orig, orig.with_suffix(".py.bak"))
                orig.write_text(patched)
                pf.unlink(missing_ok=True); mf.unlink(missing_ok=True)
                results["applied"] += 1
                results["details"].append({"file":meta["original_file"],
                                           "issue":meta.get("issue",""),"status":"applied"})
                # BUG-C5 FIX: record each applied patch in the permanent learnings store
                try:
                    from lirox.mind.agent import get_learnings
                    issue_desc = meta.get("issue", "improvement") or "improvement"
                    timestamp  = time.strftime("%Y-%m-%d %H:%M", time.localtime())
                    get_learnings().add_fact(
                        f"Fixed: {issue_desc[:120]} in {meta['original_file']} ({timestamp})",
                        confidence=1.0,
                        source="self_improve",
                    )
                except Exception:
                    pass  # learnings recording is best-effort
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"file":str(mf.name),"error":str(e)})
        return results

    def list_pending_patches(self) -> List[Dict]:
        patches = []
        for mf in sorted(self._patches_dir.glob("*.json")):
            try:
                meta = json.loads(mf.read_text())
                patches.append({"file":meta.get("original_file","?"),
                                 "issue":meta.get("issue","?")[:100],
                                 "staged":meta.get("staged_at",0)})
            except Exception: pass
        return patches

    def suggest_improvements(self) -> str:
        fs = [f"  {p} ({len((self._root/p).read_text(errors='replace').splitlines())} lines)"
              for p in self.PATCHABLE+self.AUDIT_ONLY if (self._root/p).exists()]
        et = "\n".join(f"  [{e['source']}] {e['error'][:100]}"
                        for e in self._errors[-5:]) or "  None"
        try:
            raw = generate_response(
                _SUGGEST_PROMPT.format(files_summary="\n".join(fs),errors=et),
                provider="auto", system_prompt="Suggest improvements. Output JSON.")
            raw = re.sub(r"```json?\s*|```\s*","",raw.strip())
            m   = re.search(r"\[.*\]",raw,re.DOTALL)
            if m:
                sugs = json.loads(m.group())
                lines = ["IMPROVEMENT SUGGESTIONS:\n"]
                for s in sugs[:5]:
                    lines.append(f"  [{s.get('impact','?').upper()}] {s.get('description','')}\n"
                                  f"    File: {s.get('file','?')} | {s.get('why','')}\n")
                return "\n".join(lines)
        except Exception: pass
        return "Could not generate suggestions."
