"""
Execution Planner
Converts thinking results into concrete, verifiable steps.
"""
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_logger = logging.getLogger("lirox.pipeline.planner")


@dataclass
class PipelineStep:
    """Single executable step with built-in verification."""
    action: str                  # action identifier
    params: Dict[str, Any]       # parameters passed to executor
    verify: Callable[[], bool]   # callable → True if step succeeded
    description: str             # human-readable label


@dataclass
class ExecutionPlan:
    """Complete execution plan."""
    task: str
    steps: List[PipelineStep]
    context: Dict[str, Any]
    expected_outcome: str


class ExecutionPlanner:
    """Creates concrete execution plans from task classification + thinking results."""

    def create_plan(
        self,
        query: str,
        task_type: str,
        thinking_result: Dict,
        context: Dict,
    ) -> ExecutionPlan:
        """Route to the appropriate planning strategy."""
        # SAFETY: coerce both inputs to dicts in case upstream sends wrong types
        if thinking_result is None:
            thinking_result = {"decision": query, "reasoning": "direct execution"}
        elif not isinstance(thinking_result, dict):
            _logger.warning("thinking_result is %s — coercing", type(thinking_result).__name__)
            thinking_result = {"decision": str(thinking_result)}

        if context is None:
            context = {}
        elif not isinstance(context, dict):
            _logger.warning("context is %s — coercing", type(context).__name__)
            context = {"raw": str(context)}

        if task_type == "filegen":
            return self._plan_file_generation(query, thinking_result, context)
        elif task_type == "file":
            return self._plan_file_operations(query, thinking_result, context)
        elif task_type == "shell":
            return self._plan_shell_command(query, thinking_result, context)
        elif task_type == "web":
            return self._plan_web_search(query, thinking_result, context)
        else:
            return self._plan_chat_response(query, thinking_result, context)

    # ── File Generation ──────────────────────────────────────────────────────

    def _plan_file_generation(self, query: str, thinking: Dict, context: Dict) -> ExecutionPlan:
        """
        Plan for creating rich-format files (PDF/DOCX/XLSX/PPTX/MD).

        Uses the Designer Agent pipeline:
          IntentAnalyzer → FormatEnforcer → UXStrategist → steps
        """
        # SAFETY: last-chance coercion before designer agents touch these
        if not isinstance(thinking, dict):
            thinking = {"decision": str(thinking)} if thinking else {}
        if not isinstance(context, dict):
            context = {"raw": str(context)} if context else {}

        from lirox.designer.intent_analyzer import IntentAnalyzer
        from lirox.designer.ux_strategist import UXStrategist
        from lirox.quality.format_enforcer import FormatEnforcer

        intent = IntentAnalyzer().analyze(query, context)
        file_format = FormatEnforcer().determine_format(query)
        structure = UXStrategist().design_structure(intent, file_format)
        output_path = self._determine_output_path(query, file_format)
        output_dir = os.path.dirname(output_path)

        steps: List[PipelineStep] = []

        # 1. Ensure output directory exists
        steps.append(PipelineStep(
            action="create_dir",
            params={"path": output_dir},
            verify=lambda d=output_dir: os.path.isdir(d),
            description=f"Create directory {output_dir}",
        ))

        # 2. Generate content for each section individually
        for i, section in enumerate(structure.sections):
            steps.append(PipelineStep(
                action="generate_section",
                params={
                    "section": section,
                    "intent": intent,
                    "section_index": i,
                    "total_sections": len(structure.sections),
                },
                verify=lambda: True,  # content quality checked inside executor
                description=f"Generate content: {section.name}",
            ))

        # 3. Assemble the final document
        steps.append(PipelineStep(
            action="create_document",
            params={
                "format": file_format,
                "path": output_path,
                "intent": intent,
                "structure": structure,
                # sections_content injected at runtime by pipeline/core.py
            },
            verify=lambda p=output_path: os.path.exists(p) and os.path.getsize(p) > 1000,
            description=f"Create {file_format.upper()} file: {os.path.basename(output_path)}",
        ))

        return ExecutionPlan(
            task=query,
            steps=steps,
            context={"intent": intent, "structure": structure},
            expected_outcome=f"{file_format.upper()} at {output_path}",
        )

    # ── File Operations ──────────────────────────────────────────────────────

    def _plan_file_operations(self, query: str, thinking: Dict, context: Dict) -> ExecutionPlan:
        steps: List[PipelineStep] = []
        q_lower = query.lower()

        if any(w in q_lower for w in ("read", "show", "cat", "open")):
            path = self._extract_path(query)
            steps.append(PipelineStep(
                action="read_file",
                params={"path": path},
                verify=lambda p=path: bool(p) and os.path.exists(p),
                description=f"Read {path}",
            ))

        elif any(w in q_lower for w in ("list", "show files", "ls")):
            directory = self._extract_path(query) or os.getcwd()
            steps.append(PipelineStep(
                action="list_files",
                params={"directory": directory},
                verify=lambda d=directory: os.path.isdir(d),
                description=f"List files in {directory}",
            ))

        else:
            path = self._extract_path(query) or ""
            steps.append(PipelineStep(
                action="write_file",
                params={"path": path, "query": query},
                verify=lambda p=path: bool(p) and os.path.exists(p),
                description=f"Write {path}",
            ))

        return ExecutionPlan(task=query, steps=steps, context=context,
                             expected_outcome="File operation completed")

    # ── Shell ────────────────────────────────────────────────────────────────

    def _plan_shell_command(self, query: str, thinking: Dict, context: Dict) -> ExecutionPlan:
        command = self._extract_command(query)
        return ExecutionPlan(
            task=query,
            steps=[PipelineStep(
                action="run_shell",
                params={"command": command},
                verify=lambda: True,
                description=f"Run: {command}",
            )],
            context=context,
            expected_outcome="Command executed",
        )

    # ── Web Search ───────────────────────────────────────────────────────────

    def _plan_web_search(self, query: str, thinking: Dict, context: Dict) -> ExecutionPlan:
        return ExecutionPlan(
            task=query,
            steps=[PipelineStep(
                action="web_search",
                params={"query": query},
                verify=lambda: True,
                description=f"Search web for: {query}",
            )],
            context=context,
            expected_outcome="Search results retrieved",
        )

    # ── Chat ─────────────────────────────────────────────────────────────────

    def _plan_chat_response(self, query: str, thinking: Dict, context: Dict) -> ExecutionPlan:
        return ExecutionPlan(
            task=query,
            steps=[PipelineStep(
                action="generate_chat",
                params={"query": query, "context": context},
                verify=lambda: True,
                description="Generate response",
            )],
            context=context,
            expected_outcome="Response generated",
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _determine_output_path(self, query: str, file_format: str) -> str:
        from lirox.config import WORKSPACE_DIR

        q_lower = query.lower()
        if "desktop" in q_lower:
            base_dir = os.path.expanduser("~/Desktop")
        elif "download" in q_lower:
            base_dir = os.path.expanduser("~/Downloads")
        elif "document" in q_lower:
            base_dir = os.path.expanduser("~/Documents")
        else:
            base_dir = WORKSPACE_DIR

        filename = self._extract_filename(query, file_format)
        return os.path.join(base_dir, filename)

    def _extract_filename(self, query: str, file_format: str) -> str:
        match = re.search(r'["\']([^"\']+)["\']', query)
        if match:
            name = match.group(1)
            if not name.endswith(f".{file_format}"):
                name += f".{file_format}"
            return name

        stop_words = {
            "create", "make", "generate", "a", "an", "the",
            "for", "on", "about", "pdf", "docx", "xlsx", "pptx", "md",
        }
        words = [w for w in query.lower().split() if w not in stop_words][:4]
        base = "_".join(words) if words else f"document_{int(time.time())}"
        return f"{base}.{file_format}"

    def _extract_path(self, query: str) -> Optional[str]:
        match = re.search(r'["\']([^"\']+)["\']', query)
        if match:
            return match.group(1)
        match = re.search(r'[~/\.][\w/.\-]+', query)
        if match:
            return match.group(0)
        return None

    def _extract_command(self, query: str) -> str:
        q = query.strip()
        for prefix in ("run command", "execute", "run", "shell"):
            if q.lower().startswith(prefix):
                q = q[len(prefix):].strip()
                break
        match = re.search(r'["\']([^"\']+)["\']', q)
        if match:
            return match.group(1)
        return q
