import subprocess
import shlex
from lirox.config import ALLOWED_COMMANDS, BLOCK_COMMANDS

# Patterns that indicate shell injection attempts
INJECTION_PATTERNS = ["$(", "`", " && ", " || ", "; ", " | ", " > ", " < ", "eval", "exec"]

def is_safe(cmd):
    """
    Two-layer safety check:
    1. Block dangerous commands and shell injection patterns
    2. Only allow commands on the explicit allowlist
    """
    cmd_lower = cmd.lower()

    # Check blocklist
    for blocked in BLOCK_COMMANDS:
        if blocked in cmd_lower:
            return False, f"Blocked command: '{blocked}'"

    # Check injection patterns
    for pattern in INJECTION_PATTERNS:
        if pattern in cmd:
            return False, f"Shell injection pattern detected: '{pattern}'"

    # Check allowlist
    try:
        parts = shlex.split(cmd)
        base_cmd = parts[0] if parts else ""
    except ValueError:
        return False, "Malformed command"

    if base_cmd not in ALLOWED_COMMANDS:
        return False, f"'{base_cmd}' is not in the allowed commands list: {ALLOWED_COMMANDS}"

    return True, "ok"

def run_command(cmd):
    safe, reason = is_safe(cmd)
    if not safe:
        return f"[Blocked] {reason}"

    try:
        # shell=True is needed for some basic piping if needed, but we block dangerous patterns
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=30
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        return output.strip() if output.strip() else "[Command completed with no output]"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
