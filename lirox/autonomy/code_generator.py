"""Lirox Autonomy — Code Generator.

Generates Python code that matches the style of the existing codebase:
type hints, docstrings, error handling, and imports are all included.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


TEMPLATE_MODULE = '''\
"""{module_docstring}"""
from __future__ import annotations
{imports}

{body}
'''

TEMPLATE_CLASS = '''\
class {name}:
    """{docstring}"""

{methods}
'''

TEMPLATE_FUNCTION = '''\
def {name}({params}) -> {return_type}:
    """{docstring}"""
{body}
'''


class AutoCodeGenerator:
    """Generate Python code that matches the project's existing style."""

    def __init__(self, style: Optional[Dict[str, Any]] = None) -> None:
        if style is None:
            from lirox.autonomy.code_intelligence import CodeIntelligence
            style = CodeIntelligence().detect_style()
        self.style = style

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_from_description(self, description: str, context: str = "") -> str:
        """Ask the LLM to generate code matching the project style."""
        from lirox.utils.llm import generate_response

        sys_prompt = self._build_system_prompt()
        user_prompt = (
            f"Generate Python code for the following requirement.\n\n"
            f"Requirement: {description}\n"
        )
        if context:
            user_prompt += f"\nContext / existing code:\n{context[:3000]}\n"
        user_prompt += (
            "\nRules:\n"
            "• Complete implementation — no placeholders or '...'.\n"
            "• Include all imports at the top.\n"
            "• Add type hints to every function/method.\n"
            "• Add docstrings to every class and public function.\n"
            "• Include error handling with try/except.\n"
            "• Add `if __name__ == '__main__':` demo block at the bottom.\n"
        )
        return generate_response(user_prompt, provider="auto", system_prompt=sys_prompt)

    def generate_module(
        self,
        name: str,
        docstring: str,
        imports: str,
        body: str,
    ) -> str:
        return TEMPLATE_MODULE.format(
            module_docstring=docstring,
            imports=imports,
            body=body,
        )

    def generate_class(
        self,
        name: str,
        docstring: str,
        methods: str,
    ) -> str:
        return TEMPLATE_CLASS.format(
            name=name,
            docstring=docstring,
            methods=methods,
        )

    def generate_function(
        self,
        name: str,
        params: str,
        return_type: str,
        docstring: str,
        body: str,
    ) -> str:
        indented_body = "\n".join("    " + line for line in body.splitlines())
        return TEMPLATE_FUNCTION.format(
            name=name,
            params=params,
            return_type=return_type,
            docstring=docstring,
            body=indented_body,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        hints = (
            "• Use type hints (e.g. `def foo(x: int) -> str:`).\n"
            if self.style.get("uses_type_hints") else ""
        )
        dc = (
            "• Use @dataclass where appropriate.\n"
            if self.style.get("uses_dataclass") else ""
        )
        doc_style = self.style.get("docstring_style", '"""')
        return (
            "You are an expert Python code generator.\n"
            "Generate complete, production-quality Python code:\n"
            f"{hints}{dc}"
            f"• Use {doc_style}triple-quote{doc_style} docstrings.\n"
            "• Follow PEP 8 (4-space indentation, ~100 char lines).\n"
            "• Never truncate — always write the full implementation.\n"
            "• Include error handling and logging where appropriate.\n"
        )
