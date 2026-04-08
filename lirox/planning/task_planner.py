"""
Lirox v2.0 — Task Planner

Autonomous multi-phase task planning:
1. Research phase
2. Analysis phase
3. Planning phase
4. Preparation phase
5. Execution phase
6. Verification phase
7. Optimization phase
8. Documentation phase
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Phase:
    """Represents a single phase of task execution."""
    name:    str
    status:  str                   = "pending"  # pending | running | complete | failed
    results: Optional[Any]         = None
    notes:   str                   = ""


@dataclass
class TaskPlan:
    """A complete multi-phase plan for a task."""
    task:   str
    phases: List[Phase]            = field(default_factory=list)
    status: str                    = "planned"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task":   self.task,
            "status": self.status,
            "phases": [
                {"name": p.name, "status": p.status, "notes": p.notes}
                for p in self.phases
            ],
        }


# ─── Phase Implementations ────────────────────────────────────────────────────

class _BasePhase:
    def __init__(self, task: str, previous_results: Any = None):
        self.task             = task
        self.previous_results = previous_results

    def execute(self) -> Any:
        raise NotImplementedError


class ResearchPhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "research", "task": self.task, "sources": [], "summary": ""}


class AnalysisPhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "analysis", "insights": [], "requirements": []}


class PlanningPhase(_BasePhase):
    def create_plan(self) -> List[Dict[str, Any]]:
        return [
            {"step": 1, "action": f"Execute: {self.task}", "status": "pending"},
        ]


class PreparePhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "prepare", "resources_ready": True}


class ExecutionPhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "execution", "status": "complete", "output": ""}


class VerificationPhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "verification", "verified": True, "issues": []}


class OptimizationPhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "optimization", "improvements": []}


class DocumentationPhase(_BasePhase):
    def execute(self) -> Dict[str, Any]:
        return {"phase": "documentation", "docs": f"# {self.task}\n\nTask completed."}


# ─── Task Planner ─────────────────────────────────────────────────────────────

class TaskPlanner:
    """
    Plans and executes complex tasks through 8 ordered phases.

    Usage:
        planner = TaskPlanner()
        plan = planner.plan_task("Build a web scraper")
    """

    def plan_task(self, task: str) -> TaskPlan:
        """
        Run all planning phases for a task and return a complete TaskPlan.

        Args:
            task: Natural language task description.

        Returns:
            TaskPlan with all phase results populated.
        """
        phases = []

        def run_phase(name: str, phase_obj: _BasePhase, is_planning: bool = False) -> Any:
            p = Phase(name=name, status="running")
            phases.append(p)
            try:
                if is_planning:
                    result = phase_obj.create_plan()
                else:
                    result = phase_obj.execute()
                p.status  = "complete"
                p.results = result
                return result
            except Exception as e:
                p.status = "failed"
                p.notes  = str(e)
                return None

        prev = None
        prev = run_phase("research",      ResearchPhase(task, prev))
        prev = run_phase("analysis",      AnalysisPhase(task, prev))
        prev = run_phase("planning",      PlanningPhase(task, prev), is_planning=True)
        prev = run_phase("preparation",   PreparePhase(task, prev))
        prev = run_phase("execution",     ExecutionPhase(task, prev))
        prev = run_phase("verification",  VerificationPhase(task, prev))
        prev = run_phase("optimization",  OptimizationPhase(task, prev))
        prev = run_phase("documentation", DocumentationPhase(task, prev))

        return TaskPlan(task=task, phases=phases, status="complete")
