"""Lirox Autonomy — Production-Ready Code Generator

Generates complete, style-matched Python code based on a description and
optionally validates/tests it before returning.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Generator, List, Optional

from lirox.autonomy.code_executor import CodeExecutor
from lirox.autonomy.filesystem_manager import FilesystemManager


_executor = CodeExecutor()
_fs = FilesystemManager()


class CodeGenerator:
    """Generate, validate, and optionally save production-ready Python code."""

    # ------------------------------------------------------------------
    # Style sampling
    # ------------------------------------------------------------------

    def sample_style(self, root: str, max_files: int = 5) -> str:
        """Return a condensed style sample from existing source files."""
        samples: List[str] = []
        for py_path in _fs.get_python_files(root)[:max_files]:
            ok, source = _fs.read_file(py_path)
            if ok and source.strip():
                samples.append(f"# {py_path}\n" + source[:800])
        return "\n\n---\n\n".join(samples)

    # ------------------------------------------------------------------
    # Template helpers
    # ------------------------------------------------------------------

    def _module_header(self, module_path: str, description: str) -> str:
        return (
            f'"""{description}"""\n'
            "from __future__ import annotations\n\n"
        )

    def _wrap_main_guard(self, code: str) -> str:
        """Ensure the code has a ``if __name__ == '__main__':`` guard."""
        if "__name__" not in code:
            code += '\n\nif __name__ == "__main__":\n    pass\n'
        return code

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        description: str,
        style_sample: str = "",
        extra_context: str = "",
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Generate complete Python code for *description*.

        Returns a dict with:
          - ``code``: the generated source string
          - ``valid``: True if syntax check passes
          - ``errors``: list of syntax error messages
          - ``run_result``: execution result dict (only if ``validate=True``)
        """
        from lirox.utils.llm import generate_response

        style_hint = (
            f"\n\nSTYLE REFERENCE (match this codebase's patterns):\n{style_sample[:1500]}"
            if style_sample else ""
        )
        context_hint = f"\n\nCONTEXT:\n{extra_context[:1000]}" if extra_context else ""

        system = (
            "You are a senior Python engineer. Write COMPLETE, production-ready Python code.\n"
            "Rules:\n"
            "• Include ALL imports at the top.\n"
            "• Add type hints and docstrings.\n"
            "• Include error handling.\n"
            "• Add `if __name__ == '__main__':` with a working example.\n"
            "• NEVER truncate — write the full implementation.\n"
            "• Return ONLY the Python code, no prose."
            + style_hint
        )

        prompt = f"Write complete Python code for: {description}{context_hint}"
        raw = generate_response(prompt, provider="auto", system_prompt=system)

        # Extract code block if LLM wrapped it in fences
        code = self._extract_code(raw)
        code = self._wrap_main_guard(code)

        errors = _executor.check_syntax(code)
        run_result: Optional[Dict[str, Any]] = None
        if validate and not errors:
            run_result = _executor.run_code(code, timeout=10)

        return {"code": code, "valid": not errors, "errors": errors, "run_result": run_result}

    def _extract_code(self, text: str) -> str:
        """Strip markdown code fences, returning raw Python."""
        m = re.search(r"```(?:python)?\n?([\s\S]*?)```", text)
        if m:
            return m.group(1).strip()
        return text.strip()

    # ------------------------------------------------------------------
    # Streaming interface
    # ------------------------------------------------------------------

    def generate_and_stream(
        self,
        description: str,
        root: str = "",
        save_path: str = "",
        validate: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        """Generate code and stream agent-bus events throughout the process."""
        yield {"type": "agent_progress", "message": "✍️  Generating code…"}

        style = self.sample_style(root) if root else ""
        result = self.generate(description, style_sample=style, validate=validate)

        if result["errors"]:
            yield {
                "type": "tool_result",
                "message": "⚠️  Generated code has syntax errors:",
            }
            for err in result["errors"]:
                yield {"type": "tool_result", "message": f"  {err}"}
        else:
            yield {"type": "tool_result", "message": "✓ Code syntax is valid"}

        if result.get("run_result"):
            rr = result["run_result"]
            if rr["success"]:
                yield {"type": "tool_result", "message": "✓ Code executed successfully"}
                if rr["stdout"]:
                    yield {
                        "type": "tool_result",
                        "message": rr["stdout"][:200],
                    }
            else:
                yield {
                    "type": "tool_result",
                    "message": f"⚠️  Execution warning: {rr['error'][:150]}",
                }

        if save_path and result["code"]:
            ok, msg = _fs.write_file(save_path, result["code"])
            yield {"type": "tool_result", "message": msg}

        # Yield the code as a streaming message so the UI renders it
        yield {
            "type": "streaming",
            "message": f"```python\n{result['code']}\n```",
        }
