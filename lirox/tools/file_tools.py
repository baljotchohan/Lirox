"""
Lirox v1.0.0 — File Operations and Shell Execution Tools

Safe, sandboxed file operations and shell execution.
"""
from __future__ import annotations

import os
import subprocess
from typing import Tuple


# ── File Safety ───────────────────────────────────────────────────────────────

def _is_safe_path(path: str) -> Tuple[bool, str]:
    """
    Returns (True, resolved_path) if safe, (False, reason) if blocked.
    Agent can only touch SAFE_DIRS; PROTECTED_PATHS are always blocked.
    """
    from lirox.config import SAFE_DIRS_RESOLVED, PROTECTED_PATHS
    try:
        resolved = os.path.realpath(os.path.abspath(path))
    except Exception as e:
        return False, f"Path resolution error: {e}"

    for blocked in PROTECTED_PATHS:
        if resolved.startswith(blocked):
            return False, f"BLOCKED: {blocked} is a protected system path"

    for safe in SAFE_DIRS_RESOLVED:
        if resolved.startswith(safe):
            return True, resolved

    return False, (
        f"BLOCKED: Path '{resolved}' is outside permitted directories.\n"
        f"Allowed: Desktop, Documents, Downloads, Projects, Lirox project dir"
    )


# ── File Operations ───────────────────────────────────────────────────────────

def file_read(path: str, max_chars: int = 8000) -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        lines = content.count("\n") + 1
        return f"📄 {path} ({lines} lines, {len(content)} chars):\n\n{content}"
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def file_write(path: str, content: str, mode: str = "w") -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        os.makedirs(os.path.dirname(info) or ".", exist_ok=True)
        with open(info, mode, encoding="utf-8") as f:
            f.write(content)
        return f"✅ File saved to {info} ({len(content)} chars)"
    except Exception as e:
        return f"Write error: {e}"


def file_list(path: str = ".", pattern: str = "*") -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        import glob
        matches = glob.glob(os.path.join(info, pattern), recursive=True)
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        lines = []
        for m in sorted(matches)[:100]:
            stat = os.stat(m)
            size = stat.st_size
            size_str = f"{size//1024}KB" if size > 1024 else f"{size}B"
            lines.append(f"  {'[DIR]' if os.path.isdir(m) else '':>5}  {size_str:>8}  {os.path.relpath(m, info)}")
        return f"📁 {path}:\n" + "\n".join(lines)
    except Exception as e:
        return f"List error: {e}"


def file_delete(path: str) -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        if os.path.isdir(info):
            import shutil
            shutil.rmtree(info)
            return f"🗑️  Deleted directory: {info}"
        else:
            os.remove(info)
            return f"🗑️  Deleted: {info}"
    except Exception as e:
        return f"Delete error: {e}"


def file_search(root: str, query: str) -> str:
    """Search file contents recursively for a string."""
    ok, info = _is_safe_path(root)
    if not ok:
        return info
    results = []
    for dirpath, _, filenames in os.walk(info):
        for fn in filenames:
            if fn.endswith((".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml", ".toml")):
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{os.path.relpath(fp, info)}:{i}: {line.rstrip()}")
                                if len(results) >= 50:
                                    break
                except Exception:
                    pass
        if len(results) >= 50:
            break
    if not results:
        return f"No matches for '{query}' in {root}"
    return "\n".join(results[:50]) + (f"\n… ({len(results)} total)" if len(results) == 50 else "")


# ── Shell Execution ───────────────────────────────────────────────────────────

def run_shell(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command with security validation.
    Only commands in ALLOWED_COMMANDS are permitted.
    BLOCK_PATTERNS are always rejected.
    """
    from lirox.config import ALLOWED_COMMANDS, BLOCK_PATTERNS

    # Block dangerous patterns
    for pattern in BLOCK_PATTERNS:
        if pattern.lower() in command.lower():
            return f"❌ BLOCKED: '{pattern}' is a forbidden command pattern"

    # Check first token is in allowed list
    first_token = command.strip().split()[0].lower() if command.strip() else ""
    base_cmd = os.path.basename(first_token)
    if base_cmd not in ALLOWED_COMMANDS:
        return (
            f"❌ Command '{base_cmd}' is not in the allowed list.\n"
            f"Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        if not output.strip():
            return f"✅ Command ran (no output)"
        return output.strip()[:4000]
    except subprocess.TimeoutExpired:
        return f"❌ Command timed out after {timeout}s"
    except Exception as e:
        return f"❌ Shell error: {e}"
