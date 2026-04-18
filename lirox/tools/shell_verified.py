"""Verified shell execution returning ShellReceipt.

Same allowlist + injection checks as terminal.py, but:
  - Returns a ShellReceipt (exit_code, cwd_used, verified flag).
  - Explicit cwd handling — if the requested cwd does not exist,
    fails fast instead of silently running elsewhere.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from lirox.tools.terminal import is_safe
from lirox.verify import ShellReceipt


def shell_run_verified(command: str, cwd: str = "", timeout: int = None) -> ShellReceipt:
    if timeout is None:
        from lirox.config import SHELL_TIMEOUT
        timeout = SHELL_TIMEOUT
    r = ShellReceipt(tool="shell", command=command)

    # Safety
    safe, reason = is_safe(command)
    if not safe:
        r.error = f"Blocked: {reason}"
        return r

    # Resolve cwd strictly
    cwd_used = ""
    if cwd:
        cwd_expanded = os.path.expanduser(cwd)
        if not os.path.isdir(cwd_expanded):
            r.error = f"Requested cwd does not exist: {cwd_expanded}"
            return r
        cwd_used = cwd_expanded
    r.cwd_used = cwd_used or os.getcwd()

    # Parse command
    try:
        parts = shlex.split(command)
    except ValueError as e:
        r.error = f"Parse error: {e}"
        return r
    if not parts:
        r.error = "Empty command"
        return r

    # Redirect python/python3 to the current interpreter
    if parts[0] in ("python", "python3"):
        parts[0] = sys.executable

    try:
        proc = subprocess.run(
            parts,
            capture_output=True, text=True,
            timeout=timeout,
            cwd=cwd_used or None,
        )
        r.exit_code = proc.returncode
        r.stdout    = proc.stdout or ""
        r.stderr    = proc.stderr or ""
        r.ok        = proc.returncode == 0
        r.verified  = True  # we ran it and captured real output

        out_preview = (r.stdout + (("\n" + r.stderr) if r.stderr else "")).strip()
        if len(out_preview) > 3000:
            out_preview = out_preview[:3000] + f"\n[truncated — {len(out_preview)} chars total]"
        r.message = out_preview or f"Command completed with exit {proc.returncode}"
        if not r.ok:
            r.error = f"Exit {proc.returncode}. Stderr: {r.stderr[:600]}"
        r.details["returncode"] = proc.returncode
        return r
    except subprocess.TimeoutExpired:
        r.timed_out = True
        r.error = f"Command timed out after {timeout}s"
        return r
    except Exception as e:
        r.error = f"Shell error: {e}"
        return r
