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
    2. Check that every command in a chain/pipe is on the allowlist
    """
    cmd_lower = cmd.lower().strip()

    # 1. Check blocklist (exact dangerous patterns)
    for blocked in BLOCK_COMMANDS:
        if blocked in cmd_lower:
            return False, f"Blocked command/flag: '{blocked}'"

    # 2. Check injection patterns (substitution, eval, device writes)
    for pattern in INJECTION_PATTERNS:
        if pattern in cmd:
            return False, f"Blocked injection pattern: '{pattern}'"

    # 3. Comprehensive Chain/Pipe Parsing
    # We split by all shell delimiters to ensure NO command escapes validation
    import re
    # Split by: &&, ||, ;, | (with optional surrounding whitespace)
    delimiters = r'\s*&&\s*|\s*\|\|\s*|\s*;\s*|\s*\|\s*'
    sub_commands = re.split(delimiters, cmd)

    for sub_cmd in sub_commands:
        sub_cmd = sub_cmd.strip()
        if not sub_cmd:
            continue

        try:
            # shlex.split handles quotes correctly (e.g. echo "rm -rf /")
            parts = shlex.split(sub_cmd)
            # Filter out variable assignments like VAR=val
            potential_cmd = [p for p in parts if '=' not in p]
            base_cmd = potential_cmd[0] if potential_cmd else ""
        except (ValueError, IndexError):
            return False, "Malformed command structure"

        if base_cmd and base_cmd not in ALLOWED_COMMANDS:
            # Special case for absolute paths: check the basename and directory
            import os
            basename = os.path.basename(base_cmd)
            is_absolute = os.path.isabs(base_cmd)
            
            # Strict validation for absolute paths: must be in standard system bins
            SAFE_BIN_PATHS = ["/usr/bin", "/bin", "/usr/local/bin"]
            if is_absolute:
                dirname = os.path.dirname(base_cmd)
                if dirname not in SAFE_BIN_PATHS:
                    return False, f"Untrusted execution path for binary: '{base_cmd}'"
            
            if basename not in ALLOWED_COMMANDS:
                return False, f"'{basename}' is not in the allowed commands list"

        # 4. Environment Safety check (pip/npm)
        if base_cmd in ["pip", "pip3", "npm"]:
            return False, "Autonomous environment modification blocked. Please run pip/npm commands manually in your terminal."

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
