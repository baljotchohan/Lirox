"""Runtime health diagnostics for Lirox core subsystems."""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from lirox.core.config_validator import validate_config


@dataclass
class HealthCheck:
    name: str
    ok: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    checks: List[HealthCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [
                {
                    "name": c.name,
                    "ok": c.ok,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


def run_health_checks(strict: bool = False) -> HealthReport:
    report = HealthReport()
    report.checks.append(_check_config(strict=strict))
    report.checks.append(_check_workspace())
    report.checks.append(_check_database())
    report.checks.append(_check_execution())
    report.checks.append(_check_documents())
    report.checks.append(_check_llm())
    return report


def _check_config(strict: bool) -> HealthCheck:
    try:
        cfg = validate_config(strict=strict)
        ok = cfg.is_valid
        msg = "Configuration valid" if ok else "Configuration issues found"
        return HealthCheck(
            name="config",
            ok=ok,
            message=msg,
            details={"errors": cfg.errors, "warnings": cfg.warnings, "info": cfg.info},
        )
    except Exception as exc:
        return HealthCheck(
            name="config",
            ok=False,
            message=f"Config validation error: {exc}",
        )


def _check_workspace() -> HealthCheck:
    from lirox.config import WORKSPACE_DIR, ensure_directories
    ensure_directories()
    p = Path(os.path.expanduser(WORKSPACE_DIR))
    try:
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
        can_write = os.access(str(p), os.W_OK)
        return HealthCheck(
            name="workspace",
            ok=can_write,
            message="Workspace writable" if can_write else "Workspace not writable",
            details={"path": str(p.resolve())},
        )
    except Exception as exc:
        return HealthCheck(
            name="workspace",
            ok=False,
            message=f"Workspace error: {exc}",
            details={"path": str(p)},
        )


def _check_database() -> HealthCheck:
    try:
        from lirox.database.store import DatabaseStore
        db = DatabaseStore()
        stats = db.stats()
        return HealthCheck(
            name="database",
            ok=True,
            message="SQLite store reachable",
            details=stats,
        )
    except Exception as exc:
        return HealthCheck(
            name="database",
            ok=False,
            message=f"Database unavailable: {exc}",
        )


def _check_execution() -> HealthCheck:
    try:
        from lirox.execution.runner import CodeRunner
        result = CodeRunner(timeout=5).run("print('ok')", language="python")
        return HealthCheck(
            name="execution",
            ok=result.success,
            message="Execution runner healthy" if result.success else "Execution runner failed",
            details={"output": result.output.strip(), "error": result.error.strip()},
        )
    except Exception as exc:
        return HealthCheck(
            name="execution",
            ok=False,
            message=f"Execution check failed: {exc}",
        )


def _check_documents() -> HealthCheck:
    required = ["reportlab", "pptx", "docx", "openpyxl"]
    missing = [m for m in required if importlib.util.find_spec(m) is None]
    return HealthCheck(
        name="documents",
        ok=not missing,
        message="Document dependencies installed" if not missing else "Some document dependencies are missing",
        details={"missing": missing},
    )


def _check_llm() -> HealthCheck:
    try:
        from lirox.utils.llm import available_providers
        providers = available_providers()
        return HealthCheck(
            name="llm",
            ok=bool(providers),
            message="Providers available" if providers else "No providers configured",
            details={"providers": providers},
        )
    except Exception as exc:
        return HealthCheck(
            name="llm",
            ok=False,
            message=f"LLM provider check failed: {exc}",
        )

