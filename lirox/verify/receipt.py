"""Structured execution receipts.

Every tool returns one of these instead of a plain string.
The agent's summarizer (_synth) reads `verified` and `ok` — it NEVER
narrates success unless both are True. This eliminates hallucinated
success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionReceipt:
    """Base receipt. `ok` = tool ran without exception.
    `verified` = the side effect was checked after-the-fact.
    """
    tool: str
    ok: bool = False
    verified: bool = False
    message: str = ""
    error: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def as_user_summary(self) -> str:
        """Short line for the UI/tool_result event."""
        if self.verified and self.ok:
            return f"✅ {self.message}"
        if self.ok and not self.verified:
            return f"⚠ {self.message} (unverified)"
        return f"❌ {self.error or self.message}"

    def as_llm_context(self) -> str:
        """What the summarizer LLM sees. Explicit about success/failure."""
        status = "SUCCESS_VERIFIED" if (self.verified and self.ok) else \
                 ("SUCCESS_UNVERIFIED" if self.ok else "FAILED")
        lines = [
            f"TOOL: {self.tool}",
            f"STATUS: {status}",
            f"MESSAGE: {self.message or '(none)'}",
        ]
        if self.error:
            lines.append(f"ERROR: {self.error}")
        for k, v in self.details.items():
            lines.append(f"{k.upper()}: {v}")
        return "\n".join(lines)


@dataclass
class FileReceipt(ExecutionReceipt):
    path: str = ""
    bytes_written: int = 0
    bytes_read: int = 0
    lines: int = 0
    operation: str = ""  # write / read / delete / append / patch / list / tree / mkdir


@dataclass
class ShellReceipt(ExecutionReceipt):
    command: str = ""
    cwd_used: str = ""
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass
class SkillReceipt(ExecutionReceipt):
    skill_name: str = ""
    output: str = ""
    duration_ms: int = 0


@dataclass
class AgentReceipt(ExecutionReceipt):
    agent_name: str = ""
    output: str = ""
    duration_ms: int = 0
