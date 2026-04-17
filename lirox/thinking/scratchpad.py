"""Working memory for active task execution (Dexter Scratchpad pattern)."""
from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime
from lirox.config import MAX_TOOL_RESULT_CHARS


@dataclass
class ToolCallRecord:
    tool: str
    args: Dict[str, Any]
    result: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True


class Scratchpad:
    def __init__(self):
        self.tool_results: List[ToolCallRecord] = []
        self.thinking_notes: List[str] = []

    def add_tool_result(self, tool: str, result: str, args: Dict = None):
        self.tool_results.append(
            ToolCallRecord(tool=tool, args=args or {}, result=str(result)[:MAX_TOOL_RESULT_CHARS])
        )

    def add_thinking(self, note: str):
        self.thinking_notes.append(note)

    def get_tool_results_text(self) -> str:
        if not self.tool_results:
            return ""
        return "\n\n".join(
            f"[Tool {i}: {r.tool}]\n{r.result[:MAX_TOOL_RESULT_CHARS]}"
            for i, r in enumerate(self.tool_results, 1)
        )

    def clear_oldest(self, keep: int = 3) -> int:
        if len(self.tool_results) <= keep:
            return 0
        cleared = len(self.tool_results) - keep
        self.tool_results = self.tool_results[-keep:]
        return cleared

    def reset(self):
        self.tool_results.clear()
        self.thinking_notes.clear()
