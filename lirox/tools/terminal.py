"""
Lirox v0.3 — Terminal Tool (hardened)

Safe command execution with:
- Expanded allowlist for common dev/system tools
- Smart injection detection that allows safe chaining (;) but blocks dangerous patterns
- Block-list for destructive commands
- Timeout protection
"""

import subprocess
import shlex
from lirox.config import ALLOWED_COMMANDS, BLOCK_COMMANDS

# Dangerous injection patterns — only truly dangerous ones
# We now allow safe chaining like "&&" and ";" for multi-step commands,
# but block patterns that could be used for data exfiltration or code injection
INJECTION_PATTERNS = [
    "$(", "`",          # Command substitution (arbitrary code execution)
    "eval ", "exec(",   # Code injection
    " > /dev",          # Device writes
    "| base64",         # Exfiltration
    "| curl",           # Exfiltration
]


def is_safe(cmd):
    """
    Two-layer safety check:
    1. Block dangerous commands and injection patterns
    2. Check that the base command is on the allowlist
    """
    cmd_lower = cmd.lower().strip()

    # Check blocklist (exact dangerous patterns)
    for blocked in BLOCK_COMMANDS:
        if blocked in cmd_lower:
            return False, f"Blocked command: '{blocked}'"

    # Check injection patterns
    for pattern in INJECTION_PATTERNS:
        if pattern in cmd:
            return False, f"Blocked pattern: '{pattern}'"

    # Extract the base command (first word) — handle chains
    # For chained commands (&&, ;) check ALL base commands
    # Split on && and ; to get individual commands
    sub_commands = cmd.replace("&&", ";").split(";")

    for sub_cmd in sub_commands:
        sub_cmd = sub_cmd.strip()
        if not sub_cmd:
            continue

        try:
            parts = shlex.split(sub_cmd)
            base_cmd = parts[0] if parts else ""
        except ValueError:
            return False, "Malformed command"

        if base_cmd and base_cmd not in ALLOWED_COMMANDS:
            return False, f"'{base_cmd}' is not in the allowed commands list"

    return True, "ok"


def run_command(cmd):
    """Execute a terminal command safely."""
    safe, reason = is_safe(cmd)
    if not safe:
        return f"[Blocked] {reason}"

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=60  # Increased timeout for longer ops
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        return output.strip() if output.strip() else "[Command completed with no output]"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
