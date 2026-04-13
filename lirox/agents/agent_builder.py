"""Lirox — Advanced Agent / Skill Builder.

Multi-phase builder that streams live progress events to the UI:

  Phase 1 — Deep Thinking   : Decompose requirements, design architecture
  Phase 2 — Code Generation : LLM writes the complete implementation
  Phase 3 — Validation      : Syntax + security + import checks
  Phase 4 — Test Execution  : Auto-generated tests actually run
  Phase 5 — Registration    : Save to disk and hot-reload into the registry
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Generator, List, Optional


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

_THINK_SKILL_PROMPT = """\
You are designing a Python skill module for a personal AI assistant.

USER REQUEST: {description}

Think through:
1. What inputs does this skill need?
2. What output should it return?
3. Which stdlib or common packages are needed?
4. What edge cases must be handled?
5. What is the best architecture?

Be concise. Focus on the key design decisions."""

_THINK_AGENT_PROMPT = """\
You are designing a Python sub-agent module for a personal AI assistant.

AGENT PURPOSE: {description}
AGENT NAME: {name}

Think through:
1. What queries will this agent handle?
2. What external services or data sources are needed?
3. How should results be formatted?
4. What error conditions must be handled?
5. What is the best implementation approach?

Be concise. Focus on the key design decisions."""

_BUILD_SKILL_PROMPT = """\
You are writing a Python skill module for a personal AI agent called Lirox.

USER REQUEST: {description}
DESIGN NOTES:
{thinking}

Write a complete Python module that:
1. Has SKILL_NAME = "short_name" (snake_case, no spaces)
2. Has SKILL_DESCRIPTION = "One line description"
3. Has a `run(query: str, context: dict) -> str` function
4. The run() function does exactly what the user wants and returns a string
5. Handles all errors with try/except and returns a friendly error message
6. Is self-contained (imports only stdlib or common packages)

RULES:
- No class definitions needed, just module-level code + run()
- Keep it focused on ONE thing
- Add a docstring to run()
- Never do anything destructive

Output ONLY the Python code, no markdown fences, no explanation."""

_BUILD_AGENT_PROMPT = """\
You are writing a Python sub-agent module for Lirox.

AGENT PURPOSE: {description}
AGENT NAME: {name}
DESIGN NOTES:
{thinking}

Write a complete Python module:
1. AGENT_NAME = "{name}"
2. AGENT_DESCRIPTION = "One line description of what this agent does"
3. def run(query: str, context: dict) -> str:
   - Does what the agent is supposed to do
   - Returns a string response
   - Handles all errors with try/except
   - Can use requests, stdlib, os (but NOT lirox internals)

Keep it focused and self-contained.
Output ONLY Python code, no markdown, no explanation."""

_FIX_PROMPT = """\
This Python module has a syntax or runtime error:

ERROR:
{error}

CURRENT CODE:
{code}

Fix the error. Output ONLY the corrected Python code (no markdown, no explanation)."""


# ─────────────────────────────────────────────────────────────
# AgentBuilder
# ─────────────────────────────────────────────────────────────

class AgentBuilder:
    """Multi-phase builder that constructs and validates agent/skill modules.

    All public build methods are generators that yield progress events
    compatible with the Lirox agent-bus format::

        {"type": "<event_type>", "message": "<human-readable text>"}

    The final event is always::

        {"type": "done", "answer": "<summary>", "result": {…}}

    where ``result`` contains the keys ``success``, ``name``, ``path``,
    ``code``, and (on failure) ``error``.
    """

    # ── Phase 1: Deep Thinking ────────────────────────────────────────────

    def _think(self, prompt: str) -> str:
        """Call the LLM for architectural thinking; return the trace."""
        try:
            from lirox.utils.llm import generate_response
            return generate_response(
                prompt, provider="auto",
                system_prompt="Be concise and analytical. Focus on design decisions.",
            )[:1200]
        except Exception as e:
            return f"(thinking unavailable: {e})"

    # ── Phase 3: Validation ───────────────────────────────────────────────

    def _validate(self, code: str) -> Dict[str, Any]:
        """Run syntax, import, and security checks. Returns a result dict."""
        try:
            from lirox.autonomy.code_validator import CodeValidator
            result = CodeValidator().full_check(code)
            return {
                "valid":    result.valid,
                "errors":   result.errors,
                "warnings": result.warnings,
            }
        except Exception as e:
            # Fallback: basic compile check
            try:
                compile(code, "<module>", "exec")
                return {"valid": True, "errors": [], "warnings": [str(e)]}
            except SyntaxError as se:
                return {"valid": False, "errors": [str(se)], "warnings": []}

    # ── Phase 4: Test Execution ───────────────────────────────────────────

    def _run_tests(self, code: str) -> Dict[str, Any]:
        """Generate and run tests for *code*. Returns a result dict."""
        try:
            from lirox.autonomy.code_tester import CodeTester
            return CodeTester().run_tests(code, timeout=10)
        except Exception as e:
            return {"success": False, "passed": 0, "failed": 0,
                    "errors": str(e), "output": ""}

    # ── Phase 2: Code Generation + auto-fix ──────────────────────────────

    def _generate_code(self, prompt: str) -> str:
        """Call LLM to generate code, strip fences, return raw source."""
        from lirox.utils.llm import generate_response
        raw = generate_response(
            prompt, provider="auto",
            system_prompt="You write complete, production-ready Python modules. "
                          "Output ONLY Python code.",
        )
        # Strip markdown fences if present
        raw = raw.strip()
        raw = re.sub(r"^```(?:python)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return raw.strip()

    def _try_fix(self, code: str, error: str) -> str:
        """Ask the LLM to fix a broken code snippet."""
        try:
            from lirox.utils.llm import generate_response
            fixed = generate_response(
                _FIX_PROMPT.format(error=error, code=code),
                provider="auto",
                system_prompt="Fix Python code. Output ONLY the corrected code.",
            )
            fixed = fixed.strip()
            fixed = re.sub(r"^```(?:python)?\n?", "", fixed)
            fixed = re.sub(r"\n?```$", "", fixed)
            return fixed.strip()
        except Exception:
            return code

    # ── Public: Build Skill ───────────────────────────────────────────────

    def build_skill_stream(
        self,
        description: str,
        registry: Optional[Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Build a skill module from *description*, streaming progress events.

        *registry* should be a ``SkillsRegistry`` instance used for Phase 5
        hot-reload.  If ``None``, Phase 5 is skipped.
        """
        result: Dict[str, Any] = {"success": False}

        # ── Phase 1: Deep Thinking ─────────────────────────────────────
        yield {"type": "deep_thinking", "message": "🧠 Phase 1 — Analysing requirements…"}
        thinking = self._think(_THINK_SKILL_PROMPT.format(description=description))
        for line in thinking.splitlines():
            if line.strip():
                yield {"type": "deep_thinking", "message": line}

        # ── Phase 2: Code Generation ───────────────────────────────────
        yield {"type": "code_generation", "message": "✍️  Phase 2 — Generating skill code…"}
        try:
            code = self._generate_code(
                _BUILD_SKILL_PROMPT.format(description=description, thinking=thinking)
            )
        except Exception as e:
            result["error"] = f"Code generation failed: {e}"
            yield {"type": "error", "message": result["error"]}
            yield {"type": "done", "answer": result["error"], "result": result}
            return

        # ── Phase 3: Validation ────────────────────────────────────────
        yield {"type": "code_validation", "message": "🔎 Phase 3 — Validating code…"}
        val = self._validate(code)
        for w in val.get("warnings", []):
            yield {"type": "code_validation", "message": f"⚠ {w}"}

        if not val["valid"]:
            err_str = "; ".join(val["errors"])
            yield {"type": "code_validation", "message": f"⚠ Syntax error — attempting fix…"}
            code = self._try_fix(code, err_str)
            val2 = self._validate(code)
            if not val2["valid"]:
                result["error"] = f"Validation failed: {'; '.join(val2['errors'])}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return
            yield {"type": "code_validation", "message": "✓ Fixed successfully"}

        yield {"type": "code_validation", "message": "✓ Code is valid"}

        # ── Phase 4: Test Execution ────────────────────────────────────
        yield {"type": "code_testing", "message": "🧪 Phase 4 — Running auto-generated tests…"}
        test_result = self._run_tests(code)
        if test_result.get("success"):
            yield {"type": "code_testing",
                   "message": f"✓ Tests passed ({test_result.get('passed', 0)} test(s))"}
        else:
            yield {"type": "code_testing",
                   "message": f"⚠ Tests did not pass — {test_result.get('errors', '')[:120]}"}

        # ── Phase 5: Registration ──────────────────────────────────────
        yield {"type": "self_improvement", "message": "💾 Phase 5 — Registering skill…"}
        if registry is not None:
            try:
                reg_result = registry.add_skill_from_code(code)
                if reg_result.get("success"):
                    name = reg_result.get("name", "unknown")
                    path = reg_result.get("path", "")
                    result.update({"success": True, "name": name, "path": path, "code": code})
                    yield {"type": "self_improvement",
                           "message": f"✅ Skill '{name}' registered at {path}"}
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
            # No registry — just extract the name from code
            m = re.search(r'SKILL_NAME\s*=\s*["\']([^"\']+)["\']', code)
            name = m.group(1) if m else f"skill_{int(time.time()) % 10000}"
            result.update({"success": True, "name": name, "path": "", "code": code})

        summary = f"Skill '{result.get('name')}' built successfully."
        yield {"type": "streaming", "message": summary}
        yield {"type": "done", "answer": summary, "result": result}

    # ── Public: Build Agent ───────────────────────────────────────────────

    def build_agent_stream(
        self,
        description: str,
        name: str = "CustomAgent",
        registry: Optional[Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Build a sub-agent module from *description*, streaming progress events.

        *registry* should be a ``SubAgentsRegistry`` instance used for Phase 5
        hot-reload.  If ``None``, Phase 5 is skipped.
        """
        result: Dict[str, Any] = {"success": False}
        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())

        # ── Phase 1: Deep Thinking ─────────────────────────────────────
        yield {"type": "deep_thinking", "message": "🧠 Phase 1 — Analysing agent requirements…"}
        thinking = self._think(_THINK_AGENT_PROMPT.format(description=description, name=safe_name))
        for line in thinking.splitlines():
            if line.strip():
                yield {"type": "deep_thinking", "message": line}

        # ── Phase 2: Code Generation ───────────────────────────────────
        yield {"type": "code_generation",
               "message": f"✍️  Phase 2 — Generating agent '{safe_name}'…"}
        try:
            code = self._generate_code(
                _BUILD_AGENT_PROMPT.format(
                    description=description, name=safe_name, thinking=thinking
                )
            )
        except Exception as e:
            result["error"] = f"Code generation failed: {e}"
            yield {"type": "error", "message": result["error"]}
            yield {"type": "done", "answer": result["error"], "result": result}
            return

        # ── Phase 3: Validation ────────────────────────────────────────
        yield {"type": "code_validation", "message": "🔎 Phase 3 — Validating code…"}
        val = self._validate(code)
        for w in val.get("warnings", []):
            yield {"type": "code_validation", "message": f"⚠ {w}"}

        if not val["valid"]:
            err_str = "; ".join(val["errors"])
            yield {"type": "code_validation", "message": "⚠ Syntax error — attempting fix…"}
            code = self._try_fix(code, err_str)
            val2 = self._validate(code)
            if not val2["valid"]:
                result["error"] = f"Validation failed: {'; '.join(val2['errors'])}"
                yield {"type": "error", "message": result["error"]}
                yield {"type": "done", "answer": result["error"], "result": result}
                return
            yield {"type": "code_validation", "message": "✓ Fixed successfully"}

        yield {"type": "code_validation", "message": "✓ Code is valid"}

        # ── Phase 4: Test Execution ────────────────────────────────────
        yield {"type": "code_testing", "message": "🧪 Phase 4 — Running auto-generated tests…"}
        test_result = self._run_tests(code)
        if test_result.get("success"):
            yield {"type": "code_testing",
                   "message": f"✓ Tests passed ({test_result.get('passed', 0)} test(s))"}
        else:
            yield {"type": "code_testing",
                   "message": f"⚠ Tests did not pass — {test_result.get('errors', '')[:120]}"}

        # ── Phase 5: Registration ──────────────────────────────────────
        yield {"type": "self_improvement", "message": "💾 Phase 5 — Registering agent…"}
        if registry is not None:
            try:
                reg_result = registry.add_agent_from_code(code, safe_name)
                if reg_result.get("success"):
                    reg_name = reg_result.get("name", safe_name)
                    path     = reg_result.get("path", "")
                    result.update({"success": True, "name": reg_name, "path": path, "code": code})
                    yield {"type": "self_improvement",
                           "message": f"✅ Agent '{reg_name}' registered at {path}"}
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
