"""Lirox v1.0 — Full-Stack Project Generator

Generates multi-file project scaffolds for common stacks:
  - FastAPI backend (Python)
  - React frontend (TypeScript)
  - CLI tool (Python)
  - REST API (Node.js)

All files are generated via the CodeGenerator and written to disk.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lirox.execution.generator import CodeGenerator, GeneratedCode

_logger = logging.getLogger("lirox.execution.fullstack")


@dataclass
class StackSpec:
    """Specification for a full-stack project."""
    name: str
    description: str
    stack: str = "fastapi"    # "fastapi" | "react" | "cli" | "nodejs"
    language: str = "python"
    output_dir: str = ""
    features: List[str] = field(default_factory=list)


@dataclass
class GeneratedFile:
    path: str
    code: str
    language: str
    ok: bool = True
    error: str = ""


@dataclass
class StackResult:
    spec: StackSpec
    files: List[GeneratedFile] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.files) and not self.errors

    @property
    def file_count(self) -> int:
        return len([f for f in self.files if f.ok])


_STACK_TEMPLATES: Dict[str, List[Tuple[str, str, str]]] = {
    # (relative_path, language, description_template)
    "fastapi": [
        ("main.py",           "python",     "FastAPI main application for {name}: {description}. Include routes, CORS, and lifespan."),
        ("models.py",         "python",     "Pydantic models/schemas for {name}: {description}"),
        ("database.py",       "python",     "SQLAlchemy database setup and session management for {name}"),
        ("requirements.txt",  "text",       "requirements.txt for FastAPI app named {name} using fastapi, uvicorn, sqlalchemy, pydantic"),
        ("README.md",         "markdown",   "README for {name}: {description}. Include setup and API docs."),
    ],
    "react": [
        ("src/App.tsx",       "typescript", "React App component for {name}: {description}. Use hooks, fetch API data."),
        ("src/index.tsx",     "typescript", "React entry point for {name}"),
        ("package.json",      "json",       "package.json for React TypeScript app named {name}"),
        ("tsconfig.json",     "json",       "tsconfig.json for React TypeScript project"),
        ("README.md",         "markdown",   "README for {name}: {description}. Include setup instructions."),
    ],
    "cli": [
        ("cli.py",            "python",     "Python click CLI tool for {name}: {description}. Include help text and multiple commands."),
        ("requirements.txt",  "text",       "requirements.txt for CLI tool {name}"),
        ("README.md",         "markdown",   "README for {name}: {description}. Include usage examples."),
    ],
    "nodejs": [
        ("server.js",         "javascript", "Express.js REST API for {name}: {description}. Include routes, middleware, error handler."),
        ("routes/index.js",   "javascript", "Express routes for {name}: {description}"),
        ("package.json",      "json",       "package.json for Node.js app named {name}"),
        ("README.md",         "markdown",   "README for {name}: {description}."),
    ],
}


class FullStackGenerator:
    """Generate a complete project from a :class:`StackSpec`.

    Example::

        gen = FullStackGenerator()
        spec = StackSpec(
            name="TodoAPI",
            description="A REST API for managing todo items",
            stack="fastapi",
            output_dir="/tmp/todo_api",
        )
        result = gen.generate(spec)
        print(f"Generated {result.file_count} files")
    """

    def __init__(self, provider: str = "auto"):
        self._gen = CodeGenerator(provider=provider)

    def generate(self, spec: StackSpec, write_files: bool = True) -> StackResult:
        """Generate all project files for *spec*.

        Args:
            spec:        Project specification.
            write_files: If True, write generated files to ``spec.output_dir``.

        Returns:
            :class:`StackResult` with all generated files.
        """
        result = StackResult(spec=spec)
        template_files = _STACK_TEMPLATES.get(spec.stack.lower(), _STACK_TEMPLATES["cli"])

        for rel_path, lang, desc_tmpl in template_files:
            desc = desc_tmpl.format(name=spec.name, description=spec.description)
            _logger.debug("Generating %s (%s)", rel_path, lang)

            if lang in ("text", "markdown", "json"):
                generated = self._gen.generate(lang, desc, filename=rel_path)
            else:
                generated = self._gen.generate(lang, desc, filename=rel_path)

            if generated.ok:
                gen_file = GeneratedFile(
                    path=rel_path,
                    code=generated.code,
                    language=lang,
                    ok=True,
                )
            else:
                gen_file = GeneratedFile(
                    path=rel_path, code="", language=lang,
                    ok=False, error=generated.error,
                )
                result.errors.append(f"{rel_path}: {generated.error}")

            result.files.append(gen_file)

            if write_files and gen_file.ok and spec.output_dir:
                abs_path = Path(spec.output_dir) / rel_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    abs_path.write_text(gen_file.code, encoding="utf-8")
                    gen_file.path = str(abs_path)
                except OSError as exc:
                    gen_file.ok = False
                    gen_file.error = str(exc)
                    result.errors.append(f"Write failed {rel_path}: {exc}")

        return result
