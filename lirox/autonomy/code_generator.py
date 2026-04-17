"""Lirox Autonomy — Intelligent Code Generator (Production + Agent Ready)"""

from __future__ import annotations

import re
from typing import Any, Dict, Generator, List, Optional

from lirox.autonomy.code_executor import CodeExecutor
from lirox.autonomy.filesystem_manager import FilesystemManager


_executor = CodeExecutor()
_fs = FilesystemManager()


# ─────────────────────────────────────────────────────────────
# Templates (Structure Control)
# ─────────────────────────────────────────────────────────────

TEMPLATE_MODULE = '''\
"""{module_docstring}"""
from __future__ import annotations
{imports}

{body}
'''

TEMPLATE_FUNCTION = '''\
def {name}({params}) -> {return_type}:
    """{docstring}"""
{body}
'''


# ─────────────────────────────────────────────────────────────
# Code Generator
# ─────────────────────────────────────────────────────────────

class CodeGenerator:
    """Generate, validate, and save production-ready Python code."""

    # ─────────────────────────────────────────────────────────
    # Style Learning
    # ─────────────────────────────────────────────────────────

    def sample_style(self, root: str, max_files: int = 5) -> str:
        samples: List[str] = []
        for py_path in _fs.get_python_files(root)[:max_files]:
            ok, source = _fs.read_file(py_path)
            if ok and source.strip():
                samples.append(f"# {py_path}\n" + source[:800])
        return "\n\n---\n\n".join(samples)

    # ─────────────────────────────────────────────────────────
    # LLM Generation Core
    # ─────────────────────────────────────────────────────────

    def generate(
        self,
        description: str,
        style_sample: str = "",
        extra_context: str = "",
        validate: bool = True,
    ) -> Dict[str, Any]:

        from lirox.utils.llm import generate_response

        style_hint = (
            f"\nSTYLE REFERENCE:\n{style_sample[:1500]}"
            if style_sample else ""
        )

        context_hint = (
            f"\nCONTEXT:\n{extra_context[:1000]}"
            if extra_context else ""
        )

        system = (
            "You are a senior Python engineer.\n"
            "Generate COMPLETE production-ready code.\n"
            "Rules:\n"
            "• Include imports\n"
            "• Type hints everywhere\n"
            "• Docstrings\n"
            "• Error handling\n"
            "• Add main() demo\n"
            "• No placeholders\n"
            + style_hint
        )

        prompt = f"Write Python code for: {description}{context_hint}"

        raw = generate_response(prompt, provider="auto", system_prompt=system)

        code = self._extract_code(raw)
        code = self._ensure_main(code)

        errors = _executor.check_syntax(code)

        run_result = None
        if validate and not errors:
            run_result = _executor.execute(code)

        return {
            "code": code,
            "valid": not errors,
            "errors": errors,
            "run_result": run_result,
        }

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    def _extract_code(self, text: str) -> str:
        match = re.search(r"```(?:python)?\n?([\s\S]*?)```", text)
        return match.group(1).strip() if match else text.strip()

    def _ensure_main(self, code: str) -> str:
        if "__name__" not in code:
            code += '\n\nif __name__ == "__main__":\n    pass\n'
        return code

    # ─────────────────────────────────────────────────────────
    # Streaming (Agent Mode)
    # ─────────────────────────────────────────────────────────

    def generate_and_stream(
        self,
        description: str,
        root: str = "",
        save_path: str = "",
        validate: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:

        yield {"type": "agent_progress", "message": "✍️ Generating code..."}

        style = self.sample_style(root) if root else ""

        result = self.generate(
            description,
            style_sample=style,
            validate=validate,
        )

        if result["errors"]:
            yield {"type": "error", "message": "Syntax errors found"}
            for err in result["errors"]:
                yield {"type": "error", "message": err}
        else:
            yield {"type": "success", "message": "Code is valid"}

        if result["run_result"]:
            rr = result["run_result"]
            if rr.success:
                yield {"type": "success", "message": "Execution success"}
                if rr.stdout:
                    yield {"type": "output", "message": rr.stdout[:200]}
            else:
                yield {"type": "error", "message": rr.summary()}

        if save_path:
            ok, msg = _fs.write_file(save_path, result["code"])
            yield {"type": "info", "message": msg}

        code_block = f"```python\n{result['code']}\n```"
        yield {
            "type": "streaming",
            "message": code_block,
        }
        yield {
            "type": "code",
            "message": code_block,
        }