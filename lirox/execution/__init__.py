"""Lirox v1.0 — Code Execution & Generation Package

Provides:
  - CodeGenerator: LLM-backed code generation for any language
  - CodeExecutor:  Safe sandboxed execution with timeouts
  - FullStackGenerator: Multi-file project scaffold generator
"""
from lirox.execution.generator import CodeGenerator, GeneratedCode
from lirox.execution.runner import CodeRunner, RunResult
from lirox.execution.fullstack import FullStackGenerator, StackSpec

__all__ = [
    "CodeGenerator",
    "GeneratedCode",
    "CodeRunner",
    "RunResult",
    "FullStackGenerator",
    "StackSpec",
]
