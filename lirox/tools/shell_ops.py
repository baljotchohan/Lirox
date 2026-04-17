"""Lirox v2.0.0 — Shell Operations

Executes allowed shell commands with safety checks.
No permission tiers — simple allowed-list check.

BUG-7 FIX: Removed 5-tier permission system. Uses simple allowed-list.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from lirox.config import ALLOWED_COMMANDS, BLOCK_PATTERNS, SAFE_DIRS_RESOLVED


_DEFAULT_TIMEOUT = 30


def _is_blocked(command: str) -> bool:
    """Check if a command matches any dangerous block patterns."""
    lower = command.lower()
    return any(pattern in lower for pattern in BLOCK_PATTERNS)


def _get_base_command(command: str) -> str:
    """Extract the base command name from a shell command string."""
    try:
        parts = shlex.split(command)
        if parts:
            return Path(parts[0]).name
    except ValueError:
        pass
    return command.split()[0] if command.split() else ""


def _is_allowed(command: str) -> bool:
    """Check if the base command is in the allow-list."""
    base = _get_base_command(command)
    return base in ALLOWED_COMMANDS


def run_command(command: str, cwd: str = None,
                timeout: int = _DEFAULT_TIMEOUT) -> str:
    """
    Run a shell command safely.

    Returns stdout+stderr as a string, or an error message.
    BUG-7 FIX: No permission tiers — just allowed-list check.
    """
    if not command or not command.strip():
        return "Error: Empty command."

    command = command.strip()

    if _is_blocked(command):
        return f"Error: Command blocked for safety reasons."

    if not _is_allowed(command):
        base = _get_base_command(command)
        return (
            f"Error: Command '{base}' is not in the allowed list.\n"
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS)[:15])}..."
        )

    # Validate CWD
    if cwd:
        try:
            resolved_cwd = str(Path(cwd).expanduser().resolve())
        except Exception:
            resolved_cwd = None
        if resolved_cwd:
            safe = any(
                resolved_cwd == s or resolved_cwd.startswith(s + os.sep)
                for s in SAFE_DIRS_RESOLVED
            )
            if not safe:
                return f"Error: Working directory '{cwd}' is outside safe directories."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=os.environ.copy(),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        if result.returncode != 0 and not output:
            output = f"Command exited with code {result.returncode}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s."
    except Exception as e:
        return f"Error running command: {e}"


def run_python(code: str, timeout: int = 30) -> str:
    """
    Run a Python code snippet in a subprocess.
    Writes to a temp file and executes it.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True, text=True, timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Python execution timed out after {timeout}s."
    except Exception as e:
        return f"Error running Python: {e}"
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
