"""Tests for lirox.execution — code generation and running.

The generator tests mock the LLM call so they run offline.
The runner tests execute trivial Python code in a real subprocess.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from lirox.execution.generator import (
    CodeGenerator,
    GeneratedCode,
    _clean_code,
    _infer_filename,
    _extract_dependencies,
    _validate_python_syntax,
)
from lirox.execution.runner import CodeRunner, RunResult


# ── Helper ─────────────────────────────────────────────────────────────────


def _make_generator(llm_response: str) -> CodeGenerator:
    """Return a CodeGenerator whose LLM always returns *llm_response*."""
    gen = CodeGenerator()
    with patch("lirox.execution.generator.generate_response", return_value=llm_response):
        return gen


# ── _clean_code ─────────────────────────────────────────────────────────────


class TestCleanCode:
    def test_strips_python_fence(self):
        raw = "```python\nprint('hi')\n```"
        assert _clean_code(raw, "python") == "print('hi')"

    def test_strips_generic_fence(self):
        raw = "```\ncode here\n```"
        assert _clean_code(raw, "text") == "code here"

    def test_no_fence_unchanged(self):
        raw = "x = 1"
        assert _clean_code(raw, "python") == "x = 1"

    def test_strips_title_case_fence(self):
        raw = "```Python\nimport os\n```"
        assert _clean_code(raw, "python") == "import os"


# ── _infer_filename ──────────────────────────────────────────────────────────


class TestInferFilename:
    def test_python_extension(self):
        assert _infer_filename("hello world", "python").endswith(".py")

    def test_javascript_extension(self):
        assert _infer_filename("express server", "javascript").endswith(".js")

    def test_dockerfile(self):
        assert _infer_filename("docker config", "dockerfile") == "Dockerfile"

    def test_slug_from_description(self):
        name = _infer_filename("My CLI Todo App", "python")
        assert "my_cli_todo_app" in name or "my" in name


# ── _extract_dependencies ────────────────────────────────────────────────────


class TestExtractDependencies:
    def test_extracts_third_party_python(self):
        code = "import requests\nimport os\nfrom flask import Flask"
        deps = _extract_dependencies(code, "python")
        assert "requests" in deps
        assert "flask" in deps
        assert "os" not in deps   # stdlib excluded

    def test_empty_code_returns_empty(self):
        assert _extract_dependencies("", "python") == []

    def test_javascript_deps(self):
        code = "const express = require('express');\nconst _ = require('lodash');"
        deps = _extract_dependencies(code, "javascript")
        assert "express" in deps
        assert "lodash" in deps


# ── _validate_python_syntax ──────────────────────────────────────────────────


class TestValidatePythonSyntax:
    def test_valid_code(self):
        valid, msg = _validate_python_syntax("x = 1 + 2\nprint(x)")
        assert valid
        assert msg == ""

    def test_invalid_code(self):
        valid, msg = _validate_python_syntax("def foo(:\n    pass")
        assert not valid
        assert "SyntaxError" in msg

    def test_empty_code(self):
        # Empty string is valid Python (empty module)
        valid, _ = _validate_python_syntax("")
        assert valid


# ── CodeGenerator ────────────────────────────────────────────────────────────


class TestCodeGenerator:
    def test_generate_returns_code(self):
        gen = CodeGenerator()
        mock_code = "def hello():\n    return 'world'"
        with patch("lirox.utils.llm.generate_response", return_value=mock_code):
            result = gen.generate("python", "A hello function")
        assert result.ok
        assert "def hello" in result.code

    def test_generate_strips_fences(self):
        gen = CodeGenerator()
        mock_response = "```python\nprint('hi')\n```"
        with patch("lirox.utils.llm.generate_response", return_value=mock_response):
            result = gen.generate("python", "print something")
        assert "```" not in result.code

    def test_empty_llm_response_is_error(self):
        gen = CodeGenerator()
        with patch("lirox.utils.llm.generate_response", return_value="   "):
            result = gen.generate("python", "something", max_retries=0)
        assert not result.ok
        assert result.error

    def test_generated_code_has_filename(self):
        gen = CodeGenerator()
        with patch("lirox.utils.llm.generate_response", return_value="x=1"):
            result = gen.generate("python", "counter app")
        assert result.filename.endswith(".py")

    def test_language_stored_on_result(self):
        gen = CodeGenerator()
        with patch("lirox.utils.llm.generate_response", return_value="x=1"):
            result = gen.generate("python", "test")
        assert result.language == "python"

    def test_fix_code_returns_generatedcode(self):
        gen = CodeGenerator()
        with patch("lirox.utils.llm.generate_response", return_value="x = 1"):
            result = gen.fix_code("x =", "SyntaxError", language="python")
        assert isinstance(result, GeneratedCode)

    def test_generate_tests_returns_string(self):
        gen = CodeGenerator()
        test_code = "def test_foo():\n    pass"
        with patch("lirox.utils.llm.generate_response", return_value=test_code):
            result = gen.generate_tests("def foo():\n    return 1")
        assert isinstance(result, str)


# ── CodeRunner ────────────────────────────────────────────────────────────────


class TestCodeRunner:
    def test_run_simple_python(self):
        runner = CodeRunner()
        result = runner.run("print('hello world')", language="python")
        assert result.success
        assert "hello world" in result.output

    def test_run_failing_python(self):
        runner = CodeRunner()
        result = runner.run("raise ValueError('oops')", language="python")
        assert not result.success
        assert "ValueError" in result.error or result.exit_code != 0

    def test_run_empty_code(self):
        runner = CodeRunner()
        result = runner.run("   ", language="python")
        assert not result.success
        assert result.error

    def test_timeout_respected(self):
        runner = CodeRunner(timeout=1)
        result = runner.run("import time; time.sleep(10)", language="python")
        assert not result.success
        assert result.timed_out

    def test_run_result_summary(self):
        runner = CodeRunner()
        result = runner.run("print('ok')")
        assert "ok" in result.summary

    def test_non_python_validate_only(self):
        runner = CodeRunner()
        result = runner.run("const x = 1;", language="javascript")
        # Should not crash and should return a RunResult
        assert isinstance(result, RunResult)
        assert result.language == "javascript"

    def test_python_arithmetic(self):
        runner = CodeRunner()
        result = runner.run("print(2 + 2)")
        assert result.success
        assert "4" in result.output
