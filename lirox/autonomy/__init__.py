"""Lirox Autonomy Package — Permission-aware autonomous execution and self-improvement."""

# Permission system (safety layer)
from lirox.autonomy.permission_system import (
    PermissionSystem,
    PermissionTier,
    PermissionRequest,
)

from lirox.autonomy.autonomous_resolver import AutonomousResolver

# Execution system (capabilities layer)
from lirox.autonomy.code_executor import CodeExecutor
from lirox.autonomy.filesystem_manager import FilesystemManager
from lirox.autonomy.self_improver import SelfImprover
from lirox.autonomy.code_generator import CodeGenerator

__all__ = [
    # Permission Layer
    "PermissionSystem",
    "PermissionTier",
    "PermissionRequest",
    "AutonomousResolver",

    # Execution Layer
    "CodeExecutor",
    "FilesystemManager",
    "SelfImprover",
    "CodeGenerator",
]
