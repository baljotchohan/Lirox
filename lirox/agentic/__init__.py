"""Lirox Agentic Core — a true ReAct tool-calling loop.

This package upgrades Lirox from single-shot keyword dispatch to a real
autonomous agent: the LLM plans, picks tools, observes results, and iterates
until the task is done — the same architecture used by OpenHands (CodeAct),
Claude Code, Cline and Aider, but provider-agnostic (works with groq, gemini,
ollama, anthropic, … via a JSON action protocol rather than vendor-specific
function-calling).

Public surface:
    from lirox.agentic import AgentLoop, ToolRegistry, default_registry
    from lirox.agentic import PermissionManager, PermissionMode
"""
from lirox.agentic.tools import ToolRegistry, ToolSpec, default_registry
from lirox.agentic.permissions import PermissionManager, PermissionMode
from lirox.agentic.loop import AgentLoop, AgentStep

__all__ = [
    "AgentLoop",
    "AgentStep",
    "ToolRegistry",
    "ToolSpec",
    "default_registry",
    "PermissionManager",
    "PermissionMode",
]
