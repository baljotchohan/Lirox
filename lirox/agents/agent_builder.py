"""Lirox v2.0 — Advanced Agent / Skill Builder.

Multi-phase builder with v2 upgrades:
  - Phase 1 (Think) is niche-aware — reads user profile + existing
    skills/agents so new builds fit the user's world and don't duplicate.
  - Phase 2 (Generate) includes the user's stack/tools in the prompt.
  - Phase 3 (Validate) adds: duplicate-name detection, `run()` signature
    check via AST introspection.
  - Phase 4 (Test) — failure does NOT block registration by default.
    Custom agents/skills call external APIs; auto-tests always fail them.
    Pass `allow_failed_tests=False` only if you want strict blocking.
  - Phase 5 (Register) — post-register reload verification. If import
    fails at runtime we tear down and report failure.
"""
from __future__ import annotations

import ast
import re
import time
from typing import Any, Dict, Generator, List, Optional


# ─────────────────────────────────────────────────────────────
# Prompts — niche-aware
# ─────────────────────────────────────────────────────────────

_THINK_SKILL_PROMPT = """\
You are designing a Python skill module for a personal AI assistant.

USER REQUEST: {description}

USER CONTEXT:
{profile_block}

EXISTING SKILLS (do NOT duplicate these):
{existing_skills}

Think through:
1. What inputs does this skill need?
2. What output should it return?
3. Which stdlib or common packages are needed?
4. What edge cases must be handled?
5. How does this fit the user's niche and workflow?
6. Is this actually different from an existing skill? (If not, say so.)

Be concise. Focus on the key design decisions."""

_THINK_AGENT_PROMPT = """\
You are designing a Python sub-agent module for a personal AI assistant.

AGENT PURPOSE: {description}
AGENT NAME: {name}

USER CONTEXT:
{profile_block}

EXISTING AGENTS (do NOT duplicate):
{existing_agents}

Think through:
1. What queries will this agent handle?
2. What external services or data sources are needed?
3. How should results be formatted for this user?
4. What error conditions must be handled?
5. Is this actually different from an existing agent?

Be concise. Focus on the key design decisions."""

_BUILD_SKILL_PROMPT = """\
You are writing a Python skill module for a personal AI agent called Lirox.

USER REQUEST: {description}

USER CONTEXT:
{profile_block}

DESIGN NOTES:
{thinking}

Write a complete Python module that:
1. Has SKILL_NAME = "short_name" (snake_case, no spaces)
2. Has SKILL_DESCRIPTION = "One line description"
3. Has EXACTLY this signature: def run(query: str, context: dict) -> str:
4. The run() function does exactly what the user wants and returns a string
5. Handles all errors with try/except and returns a friendly error message
6. Is self-contained (imports only stdlib or common packages: requests, json)
7. Reads user context from the `context` dict where useful (context may
   include 'user_profile', 'niche', 'current_project')

RULES:
- No class definitions needed, just module-level code + run()
- Keep it focused on ONE thing
- Add a docstring to run()
- Never do anything destructive (no rm, no shell exec, no system())

Output ONLY the Python code, no markdown fences, no explanation."""

_BUILD_AGENT_PROMPT = """\
You are writing a Python sub-agent module for Lirox.

AGENT PURPOSE: {description}
AGENT NAME: {name}

USER CONTEXT:
{profile_block}

DESIGN NOTES:
{thinking}

Write a complete Python module:
1. AGENT_NAME = "{name}"
2. AGENT_DESCRIPTION = "One line description"
3. EXACTLY this signature: def run(query: str, context: dict) -> str:
   - Returns a REAL, USEFUL string response based on the query
   - MUST produce output — never return None or empty string
   - Handles all errors with try/except, returns friendly error message
   - Uses stdlib only (json, re, datetime, pathlib, urllib, requests)
   - Reads context.get('user_profile'), context.get('niche'), context.get('current_project')
4. Include a working implementation — not just a stub

IMPORTANT: The run() function MUST return a non-empty string in ALL cases.
Add a fallback: if all else fails, return f"I processed your query: {{query}}"

Output ONLY Python code, no markdown fences, no explanation."""

_FIX_PROMPT = """\
This Python module has an error:

ERROR:
{error}

CURRENT CODE:
{code}

Fix the error. Output ONLY the corrected Python code (no markdown, no explanation)."""


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _profile_block(profile_data: Optional[Dict[str, Any]]) -> str:
    """Small context block injected into LLM prompts."""
    profile_data = profile_data or {}
    parts = []
    for k, label in [
        ("niche",           "Niche"),
        ("current_project", "Current project"),
        ("profession",      "Profession"),
    ]:
        v = profile_data.get(k, "")
        if v and v not in ("Operator", "Generalist"):
            parts.append(f"- {label}: {v}")
    niche_details = (profile_data.get("preferences") or {}).get("niche_details") or {}
    for k, v in niche_details.items():
        if v:
            parts.append(f"- {k.replace('_', ' ').title()}: {v}")
    return "\n".join(parts) or "(no profile data available)"


def _existing_skill_names(registry) -> str:
    if registry is None:
        return "(registry unavailable)"
    try:
        names = [s["name"] for s in registry.list_skills()]
        return ", ".join(names) if names else "(none)"
    except Exception:
        return "(error listing skills)"


def _existing_agent_names(registry) -> str:
    if registry is None:
        return "(registry unavailable)"
    try:
        names = [a["name"] for a in registry.list_agents()]
        return ", ".join(names) if names else "(none)"
    except Exception:
        return "(error listing agents)"


def _check_run_signature(code: str, expect_params: tuple = ("query", "context")) -> Optional[str]:
    """Introspect the AST and verify `run()` has (query, context).

    Returns None if OK, or an error string if not.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error: {e}"

    run_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            run_fn = node
            break
    if run_fn is None:
        return "Module has no run() function."

    arg_names = [a.arg for a in run_fn.args.args]
    # Accept (query, context) OR more args
    if len(arg_names) < 2:
        return f"run() takes {len(arg_names)} args; expected at least 2 (query, context)."
    if arg_names[0] != expect_params[0] or arg_names[1] != expect_params[1]:
        return (f"run() first two args are {arg_names[:2]}; "
                f"expected {list(expect_params)}.")
    return None


def _extract_name(code: str, kind: str) -> Optional[str]:
    """Extract SKILL_NAME or AGENT_NAME from code."""
    key = "SKILL_NAME" if kind == "skill" else "AGENT_NAME"
    m = re.search(rf'{key}\s*=\s*["\']([^"\']+)["\']', code)
    return m.group(1) if m else None


# ─────────────────────────────────────────────────────────────
# AgentBuilder
# ─────────────────────────────────────────────────────────────

class AgentBuilder:
    """Multi-phase builder with niche awareness and contract verification."""

    def __init__(self, profile_data: Optional[Dict[str, Any]] = None):
        self.profile_data = profile_data or {}
        # Lazy-load profile if not passed
        if not self.profile_data:
            try:
                from lirox.agent.profile import UserProfile
                self.profile_data = UserProfile().data
            except Exception:
                pass

    # ── Phase 1: Think ──────────────────────────────────────────
    def _think(self, prompt: str) -> str:
        try:
            from lirox.utils.llm import generate_response
            return generate_response(
                prompt, provider="auto",
                system_prompt="Be concise and analytical. Focus on design.",
            )[:1400]
        except Exception as e:
            return f"(thinking unavailable: {e})"

    # ── Phase 2: Generate + auto-fix ───────────────────────────
    def _generate_code(self, prompt: str) -> str:
        from lirox.utils.llm import generate_response
        raw = generate_response(
            prompt, provider="auto",
            system_prompt=(
                "You write complete, production-ready Python modules. "
                "Output ONLY Python code. Never include markdown fences."
            ),
        )
        raw = raw.strip()
        raw = re.sub(r"^```(?:python)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return raw.strip()

    def _try_fix(self, code: str, error: str) -> str:
        try:
            from lirox.utils.llm import generate_response
            fixed = generate_response(
                _FIX_PROMPT.format(error=error, code=code),
                provider="auto",
                system_prompt="Fix the code. Output only Python.",
            )
            fixed = fixed.strip()
            fixed = re.sub(r"^```(?:python)?\n?", "", fixed)
            fixed = re.sub(r"\n?```$", "", fixed)
            return fixed.strip()
        except Exception:
            return code

    # ── Phase 3: Validate ──────────────────────────────────────
    def _validate(self, code: str, kind: str,
                  registry: Optional[Any]) -> Dict[str, Any]:
        """Returns {valid, errors, warnings}."""
        errors: List[str] = []
        warnings: List[str] = []

        # 3a. Syntax via CodeValidator
        try:
            from lirox.autonomy.code_validator import CodeValidator
            result = CodeValidator().full_check(code)
            errors.extend(result.errors)
            warnings.extend(result.warnings)
        except Exception:
            try:
                compile(code, "<module>", "exec")
            except SyntaxError as se:
                errors.append(str(se))

        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        # 3b. run() signature
        sig_err = _check_run_signature(code)
        if sig_err:
            errors.append(f"Signature check: {sig_err}")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # 3c. duplicate-name check
        name = _extract_name(code, kind)
        if name and registry is not None:
            try:
                if kind == "skill":
                    existing = [s["name"] for s in registry.list_skills()]
                else:
                    existing = [a["name"] for a in registry.list_agents()]
                if name in existing:
                    warnings.append(
                        f"A {kind} named '{name}' already exists. Registering "
                        f"will overwrite it."
                    )
            except Exception:
                pass

        return {"valid": True, "errors": errors, "warnings": warnings}

    # ── Phase 4: Test ──────────────────────────────────────────
    def _run_tests(self, code: str) -> Dict[str, Any]:
        try:
            from lirox.autonomy.code_tester import CodeTester
            return CodeTester().run_tests(code, timeout=10)
        except Exception as e:
            return {"success": False, "passed": 0, "failed": 0,
                    "errors": str(e), "output": ""}

    # ── Phase 5: Reload verification ──────────────────────────
    def _verify_reload(self, kind: str, registry: Optional[Any], name: str) -> bool:
        """After registration, confirm the module actually loaded."""
        if registry is None:
            return True  # no registry → skip
        try:
            if kind == "skill":
                names = [s["name"] for s in registry.list_skills()]
            else:
                names = [a["name"] for a in registry.list_agents()]
            return name in names
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────
    # Public: Build Skill
    # ─────────────────────────────────────────────────────────

    def build_skill_stream(
        self,
        description: str,
        registry: Optional[Any] = None,
        allow_failed_tests: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        result: Dict[str, Any] = {"success": False}
        profile_block = _profile_block(self.profile_data)
        existing = _existing_skill_names(registry)

        # Phase 1
        yield {"type": "deep_thinking",
               "message": "🧠 Phase 1 — Analysing requirements (niche-aware)…"}
        thinking = self._think(_THINK_SKILL_PROMPT.format(
            description=description, profile_block=profile_block,
            existing_skills=existing,
        ))
        for line in thinking.splitlines():
            if line.strip():
                yield {"type": "deep_thinking", "message": line}

        # Phase 2
        yield {"type": "code_generation", "message": "✍️ Phase 2 — Generating skill code…"}
        try:
            code = self._generate_code(_BUILD_SKILL_PROMPT.format(
                description=description, profile_block=profile_block,
                thinking=thinking,
            ))
        except Exception as e:
            result["error"] = f"Code generation failed: {e}"
            yield {"type": "error", "message": result["error"]}
            yield {"type": "done", "answer": result["error"], "result": result}
            return

        # Phase 3
        yield {"type": "code_validation", "message": "🔎 Phase 3 — Validating code + contract…"}
        val = self._validate(code, kind="skill", registry=registry)
        for w in val["warnings"]:
            yield {"type": "code_validation", "message": f"⚠ {w}"}

        if not val["valid"]:
            err_str = "; ".join(val["errors"])
            yield {"type": "code_validation", "message": "⚠ Issue — attempting fix…"}
            code = self._try_fix(code, err_str)
            val2 = self._validate(code, kind="skill", registry=registry)
            if not val2["valid"]:
                result["error"] = f"Validation failed: {'; '.join(val2['errors'])}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return
            yield {"type": "code_validation", "message": "✓ Fixed successfully"}

        yield {"type": "code_validation", "message": "✓ Code is valid and contract-compliant"}

        # Phase 4
        yield {"type": "code_testing", "message": "🧪 Phase 4 — Running auto-generated tests…"}
        test_result = self._run_tests(code)
        if test_result.get("success"):
            yield {"type": "code_testing",
                   "message": f"✓ Tests passed ({test_result.get('passed', 0)})"}
        else:
            err_snip = str(test_result.get("errors", ""))[:200]
            if allow_failed_tests:
                yield {"type": "code_testing",
                       "message": f"⚠ Tests failed but registration allowed: {err_snip}"}
            else:
                result["error"] = f"Tests failed (registration blocked): {err_snip}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return

        # Phase 5
        yield {"type": "self_improvement", "message": "💾 Phase 5 — Registering skill…"}
        if registry is not None:
            try:
                reg_result = registry.add_skill_from_code(code)
                if reg_result.get("success"):
                    name = reg_result.get("name", "unknown")
                    path = reg_result.get("path", "")
                    if not self._verify_reload("skill", registry, name):
                        result["error"] = (
                            f"Skill written to {path} but failed to load. "
                            f"Check the file for runtime errors."
                        )
                        yield {"type": "error", "message": result["error"]}
                        yield {"type": "done", "answer": result["error"], "result": result}
                        return
                    result.update({"success": True, "name": name, "path": path, "code": code})
                    yield {"type": "self_improvement",
                           "message": f"✅ Skill '{name}' registered + reload verified at {path}"}
                else:
                    result["error"] = reg_result.get("error", "Registration failed")
                    yield {"type": "error", "message": result["error"]}
                    yield {"type": "done", "answer": result["error"], "result": result}
                    return
            except Exception as e:
                result["error"] = f"Registration error: {e}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return
        else:
            name = _extract_name(code, "skill") or f"skill_{int(time.time()) % 10000}"
            result.update({"success": True, "name": name, "path": "", "code": code})

        summary = f"Skill '{result.get('name')}' built successfully."
        yield {"type": "streaming", "message": summary}
        yield {"type": "done", "answer": summary, "result": result}

    # ─────────────────────────────────────────────────────────
    # Public: Build Agent
    # ─────────────────────────────────────────────────────────

    def build_agent_stream(
        self,
        description: str,
        name: str = "CustomAgent",
        registry: Optional[Any] = None,
        allow_failed_tests: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        result: Dict[str, Any] = {"success": False}
        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())
        profile_block = _profile_block(self.profile_data)
        existing = _existing_agent_names(registry)

        yield {"type": "deep_thinking",
               "message": f"🧠 Phase 1 — Analysing agent '{safe_name}' (niche-aware)…"}
        thinking = self._think(_THINK_AGENT_PROMPT.format(
            description=description, name=safe_name,
            profile_block=profile_block, existing_agents=existing,
        ))
        for line in thinking.splitlines():
            if line.strip():
                yield {"type": "deep_thinking", "message": line}

        yield {"type": "code_generation",
               "message": f"✍️ Phase 2 — Generating agent '{safe_name}'…"}
        try:
            code = self._generate_code(_BUILD_AGENT_PROMPT.format(
                description=description, name=safe_name,
                profile_block=profile_block, thinking=thinking,
            ))
        except Exception as e:
            result["error"] = f"Code generation failed: {e}"
            yield {"type": "error", "message": result["error"]}
            yield {"type": "done", "answer": result["error"], "result": result}
            return

        yield {"type": "code_validation", "message": "🔎 Phase 3 — Validating code + contract…"}
        val = self._validate(code, kind="agent", registry=registry)
        for w in val["warnings"]:
            yield {"type": "code_validation", "message": f"⚠ {w}"}

        if not val["valid"]:
            err_str = "; ".join(val["errors"])
            yield {"type": "code_validation", "message": "⚠ Issue — attempting fix…"}
            code = self._try_fix(code, err_str)
            val2 = self._validate(code, kind="agent", registry=registry)
            if not val2["valid"]:
                result["error"] = f"Validation failed: {'; '.join(val2['errors'])}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return
            yield {"type": "code_validation", "message": "✓ Fixed successfully"}

        yield {"type": "code_validation", "message": "✓ Code is valid and contract-compliant"}

        yield {"type": "code_testing", "message": "🧪 Phase 4 — Running auto-generated tests…"}
        test_result = self._run_tests(code)
        if test_result.get("success"):
            yield {"type": "code_testing",
                   "message": f"✓ Tests passed ({test_result.get('passed', 0)})"}
        else:
            err_snip = str(test_result.get("errors", ""))[:200]
            if allow_failed_tests:
                yield {"type": "code_testing",
                       "message": f"⚠ Tests failed but registration allowed: {err_snip}"}
            else:
                result["error"] = f"Tests failed (registration blocked): {err_snip}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return

        yield {"type": "self_improvement", "message": "💾 Phase 5 — Registering agent…"}
        if registry is not None:
            try:
                reg_result = registry.add_agent_from_code(code, safe_name)
                if reg_result.get("success"):
                    reg_name = reg_result.get("name", safe_name)
                    path     = reg_result.get("path", "")
                    if not self._verify_reload("agent", registry, reg_name):
                        result["error"] = (
                            f"Agent written to {path} but failed to load. "
                            f"Check for runtime errors."
                        )
                        yield {"type": "error", "message": result["error"]}
                        yield {"type": "done", "answer": result["error"], "result": result}
                        return
                    result.update({"success": True, "name": reg_name,
                                    "path": path, "code": code})
                    yield {"type": "self_improvement",
                           "message": f"✅ Agent '{reg_name}' registered + reload verified at {path}"}
                else:
                    result["error"] = reg_result.get("error", "Registration failed")
                    yield {"type": "error", "message": result["error"]}
                    yield {"type": "done", "answer": result["error"], "result": result}
                    return
            except Exception as e:
                result["error"] = f"Registration error: {e}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return
        else:
            result.update({"success": True, "name": safe_name, "path": "", "code": code})

        summary = f"Agent '{result.get('name')}' built successfully."
        yield {"type": "streaming", "message": summary}
        yield {"type": "done", "answer": summary, "result": result}
