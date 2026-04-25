"""
Core Execution Pipeline
Orchestrates: CLASSIFY → THINK → PLAN → EXECUTE → VERIFY → RESPOND
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

_logger = logging.getLogger("lirox.pipeline")


@dataclass
class PipelineEvent:
    """Events emitted during pipeline execution."""
    type: str  # "progress", "thinking", "plan", "execute", "verify", "done", "error"
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ExecutionPipeline:
    """
    Main execution pipeline.
    Replaces the broken classify → execute flow with proper staged execution.

    Stages:
        1. CLASSIFY  – determine task type and complexity
        2. FILTER    – strip irrelevant profile context
        3. THINK     – adaptive reasoning (skipped for simple tasks)
        4. PLAN      – build concrete, verifiable steps
        5. EXECUTE   – run steps, collect receipts
        6. VERIFY    – check actual system state
        7. RESPOND   – build honest success / failure message
    """

    def __init__(self, memory, profile_data: Dict[str, Any]):
        self.memory = memory
        self.profile_data = profile_data

        # Lazy-loaded subsystems (avoids circular imports at module load time)
        self._thinker = None
        self._planner = None
        self._executor = None
        self._verifier = None
        self._context_filter = None
        self._format_enforcer = None

    # ─── lazy properties ────────────────────────────────────────────────────

    @property
    def thinker(self):
        if self._thinker is None:
            from lirox.thinking.adaptive_engine import AdaptiveThinkingEngine
            self._thinker = AdaptiveThinkingEngine()
        return self._thinker

    @property
    def planner(self):
        if self._planner is None:
            from lirox.pipeline.planner import ExecutionPlanner
            self._planner = ExecutionPlanner()
        return self._planner

    @property
    def executor(self):
        if self._executor is None:
            from lirox.pipeline.executor import StepExecutor
            self._executor = StepExecutor()
        return self._executor

    @property
    def verifier(self):
        if self._verifier is None:
            from lirox.pipeline.verifier import SystemVerifier
            self._verifier = SystemVerifier()
        return self._verifier

    @property
    def context_filter(self):
        if self._context_filter is None:
            from lirox.quality.context_filter import ContextFilter
            self._context_filter = ContextFilter()
        return self._context_filter

    @property
    def format_enforcer(self):
        if self._format_enforcer is None:
            from lirox.quality.format_enforcer import FormatEnforcer
            self._format_enforcer = FormatEnforcer()
        return self._format_enforcer

    # ─── main entry point ───────────────────────────────────────────────────

    def run(self, query: str, context: str = "") -> Generator[PipelineEvent, None, None]:
        """
        Execute complete pipeline for a query.
        Yields PipelineEvent objects for UI rendering.
        """
        start_time = time.time()

        try:
            # ══════════════════════════════════════════════════════════
            # STAGE 1: CLASSIFY
            # ══════════════════════════════════════════════════════════
            yield PipelineEvent("progress", "📋 Classifying task...")

            task_type, complexity = self._classify(query)
            yield PipelineEvent("progress", f"Task: {task_type} | Complexity: {complexity}")

            # ══════════════════════════════════════════════════════════
            # STAGE 2: CONTEXT FILTERING
            # ══════════════════════════════════════════════════════════

            # SAFETY: conversation_context must always be a plain string
            safe_context_str = context if isinstance(context, str) else str(context)

            filtered_context = self.context_filter.filter(
                query=query,
                task_type=task_type,
                user_profile=self.profile_data or {},
                conversation_context=safe_context_str,
            )

            # SAFETY: filtered_context must always be a dict
            if not isinstance(filtered_context, dict):
                _logger.warning(
                    "Context filter returned %s — coercing to dict",
                    type(filtered_context).__name__,
                )
                filtered_context = {"data": filtered_context} if filtered_context else {}

            # ══════════════════════════════════════════════════════════
            # STAGE 3: THINK (adaptive — skipped for simple tasks)
            # ══════════════════════════════════════════════════════════
            thinking_result: Optional[Dict] = None

            if complexity in ("medium", "high"):
                yield PipelineEvent("progress", "🧠 Thinking about approach...")

                for event in self.thinker.think(query, filtered_context, complexity):
                    yield PipelineEvent("thinking", event.get("message", ""), event)
                    if event.get("type") == "done":
                        thinking_result = event.get("data")
            else:
                thinking_result = {
                    "decision": query,
                    "reasoning": "Direct execution",
                    "approach": "straightforward",
                }

            # ══════════════════════════════════════════════════════════
            # STAGE 4: PLAN
            # ══════════════════════════════════════════════════════════
            yield PipelineEvent("progress", "📝 Creating execution plan...")

            plan = self.planner.create_plan(
                query=query,
                task_type=task_type,
                thinking_result=thinking_result,
                context=filtered_context,
            )

            yield PipelineEvent("plan", f"Plan created: {len(plan.steps)} steps", {
                "steps": [s.description for s in plan.steps]
            })
            for i, step in enumerate(plan.steps, 1):
                yield PipelineEvent("progress", f"  {i}. {step.description}")

            # ══════════════════════════════════════════════════════════
            # STAGE 5: EXECUTE
            # ══════════════════════════════════════════════════════════
            yield PipelineEvent("progress", "⚙️ Executing plan...")

            receipts = []
            sections_content: List[Dict] = []  # Collects generated sections for assembly

            for i, step in enumerate(plan.steps, 1):
                yield PipelineEvent("execute", f"Step {i}/{len(plan.steps)}: {step.description}")

                # Pass accumulated section content into create_document step
                if step.action == "create_document":
                    step.params["sections_content"] = sections_content

                receipt = self.executor.execute(step)
                receipts.append(receipt)

                if not receipt.success:
                    yield PipelineEvent("error", f"Step {i} failed: {receipt.error}")
                    break

                # Accumulate section content
                if step.action == "generate_section" and receipt.success:
                    sections_content.append(receipt.data)

                yield PipelineEvent("execute", f"✓ Step {i} complete")

            # ══════════════════════════════════════════════════════════
            # STAGE 6: VERIFY
            # ══════════════════════════════════════════════════════════
            yield PipelineEvent("progress", "🔍 Verifying results...")

            verification = self.verifier.verify_all(plan.steps, receipts)

            for i, detail in verification.details.items():
                yield PipelineEvent("verify", detail)

            # ══════════════════════════════════════════════════════════
            # STAGE 7: RESPOND
            # ══════════════════════════════════════════════════════════
            elapsed = time.time() - start_time

            if verification.all_passed:
                response = self._build_success_response(plan, verification, receipts)
                yield PipelineEvent("done", response, {
                    "success": True,
                    "elapsed": elapsed,
                    "steps_completed": len(verification.passed_steps),
                })
            else:
                response = self._build_failure_response(plan, verification, receipts)
                yield PipelineEvent("error", response, {
                    "success": False,
                    "elapsed": elapsed,
                    "failed_steps": verification.failed_steps,
                })

        except Exception as e:
            _logger.error("Pipeline error: %s", e, exc_info=True)
            yield PipelineEvent("error", f"Pipeline failure: {e}")

    # ─── private helpers ────────────────────────────────────────────────────

    def _classify(self, query: str):
        """Return (task_type, complexity)."""
        from lirox.agents.personal_agent import _classify as classify_task

        task_type = classify_task(query)
        q_lower = query.lower()

        if task_type == "chat" and len(query.split()) < 10:
            complexity = "low"
        elif task_type in ("shell", "file") and not any(
            w in q_lower for w in ("multiple", "complex", "all", "entire")
        ):
            complexity = "low"
        elif task_type == "filegen" or "full stack" in q_lower or "complete" in q_lower:
            complexity = "high"
        else:
            complexity = "medium"

        return task_type, complexity

    def _build_success_response(self, plan, verification, receipts) -> str:
        lines = [f"✅ Completed: {plan.task}"]
        lines.append("")
        for receipt in receipts:
            if receipt.success and receipt.data:
                if "path" in receipt.data:
                    path = receipt.data["path"]
                    size = receipt.data.get("size", 0)
                    size_kb = size / 1024 if size > 0 else 0
                    lines.append(f"  📄 {path} ({size_kb:.1f} KB)")
                elif "output" in receipt.data:
                    lines.append(f"  ✓ {str(receipt.data['output'])[:100]}")
        return "\n".join(lines)

    def _build_failure_response(self, plan, verification, receipts) -> str:
        lines = [f"❌ Failed: {plan.task}"]
        lines.append("")
        for i in verification.failed_steps:
            detail = verification.details.get(i, "Unknown error")
            lines.append(f"  Step {i + 1} failed: {detail}")
        return "\n".join(lines)
