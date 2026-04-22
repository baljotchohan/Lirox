"""Lirox v1.0 — Code Generation Engine

LLM-backed code generator with:
  - Language-aware prompting (Python, JavaScript, Go, Rust, TypeScript, etc.)
  - Complete implementation enforcement (no truncation, no placeholders)
  - Automatic filename inference
  - Syntax validation before returning
  - Retry logic on failed attempts
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

_logger = logging.getLogger("lirox.execution.generator")

# Languages where we can do syntax validation
_VALIDATABLE = {"python"}

# Common language aliases
_LANG_ALIASES: dict[str, str] = {
    "py":         "python",
    "js":         "javascript",
    "ts":         "typescript",
    "tsx":        "typescript",
    "jsx":        "javascript",
    "rb":         "ruby",
    "rs":         "rust",
    "sh":         "bash",
    "bash":       "bash",
    "shell":      "bash",
    "dockerfile": "dockerfile",
    "yml":        "yaml",
    "yaml":       "yaml",
}


@dataclass
class GeneratedCode:
    """Result of a code generation request."""
    language: str
    code: str
    filename: str = ""
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    tests: str = ""
    valid_syntax: bool = True
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.code.strip()) and not self.error


class CodeGenerator:
    """Generate complete, production-quality code using the configured LLM.

    Example::

        gen = CodeGenerator()
        result = gen.generate("python", "A CLI todo-list app with SQLite storage")
        print(result.code)
    """

    # System prompt constants
    _SYSTEM = (
        "You are Lirox, an expert programmer. Write COMPLETE, production-quality code.\n"
        "RULES:\n"
        "1. Write the FULL implementation — never use '...', 'TODO', or placeholders.\n"
        "2. Include all imports at the top.\n"
        "3. Include a brief usage example in a comment or __main__ block.\n"
        "4. Follow idiomatic style for the target language.\n"
        "5. Return ONLY the code — no explanations, no markdown fences.\n"
    )

    def __init__(self, provider: str = "auto"):
        self._provider = provider

    def generate(
        self,
        language: str,
        description: str,
        context: str = "",
        filename: str = "",
        max_retries: int = 2,
    ) -> GeneratedCode:
        """Generate code for *description* in *language*.

        Args:
            language:    Target programming language.
            description: What the code should do.
            context:     Optional extra context (file structure, APIs, etc.).
            filename:    Suggested output filename (inferred if empty).
            max_retries: How many times to retry on empty/invalid output.

        Returns:
            :class:`GeneratedCode` — always returned, check ``.ok``.
        """
        lang = _LANG_ALIASES.get(language.lower(), language.lower())
        inferred_filename = filename or _infer_filename(description, lang)

        prompt = _build_prompt(lang, description, context, inferred_filename)

        code = ""
        last_error = ""
        for attempt in range(1, max_retries + 2):
            try:
                from lirox.utils.llm import generate_response
                raw = generate_response(
                    prompt,
                    provider=self._provider,
                    system_prompt=self._SYSTEM,
                )
                code = _clean_code(raw, lang)
                if code.strip():
                    break
            except Exception as exc:
                last_error = str(exc)
                _logger.warning("Code generation attempt %d failed: %s", attempt, exc)
                if attempt > max_retries:
                    break

        if not code.strip():
            return GeneratedCode(
                language=lang,
                code="",
                filename=inferred_filename,
                error=last_error or "LLM returned empty response",
            )

        # Syntax validation for Python
        valid, syn_error = True, ""
        if lang in _VALIDATABLE:
            valid, syn_error = _validate_python_syntax(code)

        # Auto-generate test skeleton for Python
        tests = ""
        if lang == "python":
            tests = _skeleton_tests(code, inferred_filename)

        # Extract dependencies hint
        deps = _extract_dependencies(code, lang)

        return GeneratedCode(
            language=lang,
            code=code,
            filename=inferred_filename,
            description=description,
            dependencies=deps,
            tests=tests,
            valid_syntax=valid,
            error=syn_error if not valid else "",
        )

    def generate_tests(self, code: str, language: str = "python") -> str:
        """Generate a test file for existing *code*."""
        lang = _LANG_ALIASES.get(language.lower(), language.lower())
        if lang != "python":
            return f"# Test generation for {lang} not yet supported"

        prompt = (
            f"Write pytest tests for the following Python code.\n"
            f"Import the module and test every function / class.\n"
            f"Return ONLY the test code, no markdown.\n\n"
            f"```python\n{code[:4000]}\n```"
        )
        try:
            from lirox.utils.llm import generate_response
            raw = generate_response(prompt, provider=self._provider, system_prompt=self._SYSTEM)
            return _clean_code(raw, "python")
        except Exception as exc:
            return f"# Test generation failed: {exc}"

    def fix_code(self, code: str, error: str, language: str = "python") -> GeneratedCode:
        """Attempt to fix *code* given the *error* message.

        Returns a new :class:`GeneratedCode` with the corrected code.
        """
        lang = _LANG_ALIASES.get(language.lower(), language.lower())
        prompt = (
            f"Fix the following {lang} code that has this error:\n\n"
            f"ERROR:\n{error[:1000]}\n\n"
            f"CODE:\n```{lang}\n{code[:4000]}\n```\n\n"
            f"Return ONLY the fixed code with no markdown fences."
        )
        try:
            from lirox.utils.llm import generate_response
            raw = generate_response(prompt, provider=self._provider, system_prompt=self._SYSTEM)
            fixed = _clean_code(raw, lang)
            valid, syn_err = (True, "") if lang not in _VALIDATABLE else _validate_python_syntax(fixed)
            return GeneratedCode(
                language=lang,
                code=fixed,
                description=f"Fixed: {error[:100]}",
                valid_syntax=valid,
                error=syn_err if not valid else "",
            )
        except Exception as exc:
            return GeneratedCode(language=lang, code=code, error=str(exc))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_prompt(lang: str, description: str, context: str, filename: str) -> str:
    parts = [f"Write {lang} code: {description}"]
    if filename:
        parts.append(f"Filename: {filename}")
    if context:
        parts.append(f"Context:\n{context[:2000]}")
    parts.append("Return ONLY the raw code. No markdown. No fences. No explanations.")
    return "\n\n".join(parts)


def _clean_code(text: str, lang: str) -> str:
    """Strip markdown fences and normalise whitespace."""
    text = text.strip()
    for fence in (f"```{lang}", f"```{lang.title()}", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            break
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _infer_filename(description: str, lang: str) -> str:
    _EXTS: dict[str, str] = {
        "python":     "py",
        "javascript": "js",
        "typescript": "ts",
        "rust":       "rs",
        "go":         "go",
        "ruby":       "rb",
        "bash":       "sh",
        "dockerfile": "Dockerfile",
        "yaml":       "yml",
        "html":       "html",
        "css":        "css",
        "sql":        "sql",
    }
    ext = _EXTS.get(lang, lang)
    # Convert description to snake_case filename
    slug = re.sub(r"[^a-z0-9]+", "_", description.lower()[:40]).strip("_")
    if not slug:
        slug = "generated"
    if ext == "Dockerfile":
        return "Dockerfile"
    return f"{slug}.{ext}"


def _validate_python_syntax(code: str) -> tuple[bool, str]:
    import ast, textwrap
    try:
        ast.parse(textwrap.dedent(code))
        return True, ""
    except SyntaxError as exc:
        return False, f"SyntaxError at line {exc.lineno}: {exc.msg}"
    except Exception as exc:
        return False, str(exc)


def _extract_dependencies(code: str, lang: str) -> list[str]:
    deps: list[str] = []
    if lang == "python":
        for match in re.finditer(r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", code, re.M):
            top = match.group(1).split(".")[0]
            stdlib = {"os", "sys", "re", "json", "math", "time", "datetime", "pathlib",
                      "typing", "dataclasses", "collections", "itertools", "functools",
                      "abc", "io", "threading", "subprocess", "shutil", "tempfile",
                      "hashlib", "base64", "uuid", "random", "string", "copy",
                      "logging", "warnings", "contextlib", "ast", "textwrap"}
            if top not in stdlib and top not in deps:
                deps.append(top)
    elif lang == "javascript":
        for match in re.finditer(r"""(?:require\(['"]|from\s+['"])([^'"./][^'"]*)""", code):
            pkg = match.group(1).split("/")[0]
            if pkg not in deps:
                deps.append(pkg)
    return deps[:20]


def _skeleton_tests(code: str, filename: str) -> str:
    module = filename.replace(".py", "").replace("/", ".").replace("\\", ".")
    fns = re.findall(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code, re.M)
    lines = [f"import pytest", f"# from {module} import ...", ""]
    for fn in fns[:10]:
        if not fn.startswith("_"):
            lines += [f"def test_{fn}():", f"    # TODO: test {fn}", "    pass", ""]
    return "\n".join(lines)
