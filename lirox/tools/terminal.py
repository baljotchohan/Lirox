"""
Lirox v3.0 — Terminal Tool (hardened)

Safe command execution with:
- Expanded allowlist for common dev/system tools
- Smart injection detection that allows safe chaining (;) but blocks dangerous patterns
- Block-list for destructive commands
- Timeout protection
"""

import subprocess
import os
import re
import sys
import shlex
from lirox.config import ALLOWED_COMMANDS, BLOCK_PATTERNS

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
    for blocked in BLOCK_PATTERNS:
        if blocked in cmd_lower:
            return False, f"Blocked command/flag: '{blocked}'"

    # 2. Check injection patterns (substitution, eval, device writes)
    for pattern in INJECTION_PATTERNS:
        if pattern in cmd:
            return False, f"Blocked injection pattern: '{pattern}'"

    # 3. Comprehensive Chain/Pipe Parsing
    # We split by all shell delimiters to ensure NO command escapes validation
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
            # Filter out variable assignments like VAR=val or VAR="val=with=equals"
            # A token is a variable assignment if it starts with a valid identifier
            # followed immediately by '=', regardless of the value after the '='.
            potential_cmd = []
            for p in parts:
                # Match shell variable assignment: IDENTIFIER=...
                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', p):
                    continue  # skip — this is an assignment, not a command
                potential_cmd.append(p)
            base_cmd = potential_cmd[0] if potential_cmd else ""
        except (ValueError, IndexError):
            return False, "Malformed command structure"

        if base_cmd and base_cmd not in ALLOWED_COMMANDS:
            # Special case for absolute paths: check the basename and directory
            basename = os.path.basename(base_cmd)
            is_absolute = os.path.isabs(base_cmd)
            
            # Strip .exe for basename checking on Windows
            if os.name == 'nt' and basename.lower().endswith('.exe'):
                basename = basename[:-4]
            
            # Strict validation for absolute paths: must be in standard system bins
            if is_absolute and os.name != 'nt':
                SAFE_BIN_PATHS = ["/usr/bin", "/bin", "/usr/local/bin"]
                dirname = os.path.dirname(base_cmd)
                if dirname not in SAFE_BIN_PATHS:
                    return False, f"Untrusted execution path for binary: '{base_cmd}'"
            
            if basename not in ALLOWED_COMMANDS:
                return False, f"'{basename}' is not in the allowed commands list"

 

    return True, "ok"


def run_command(cmd: str) -> str:
    """
    Execute a terminal command safely using shlex parsing (no shell=True).
    
    [FIX #1] Prevents shell injection by using subprocess array form.
    [FIX #2] Uses sys.executable for python3 commands to avoid Xcode resolver.
    """
    safe, reason = is_safe(cmd)
    if not safe:
        return f"[Blocked] {reason}"

    try:
        parsed_args = shlex.split(cmd)

        # [FIX #2] Replace python3/python with sys.executable so scripts always
        # run under the same interpreter Lirox is using (not the Xcode fallback)
        if parsed_args and parsed_args[0] in ("python3", "python"):
            parsed_args[0] = sys.executable

        result = subprocess.run(
            parsed_args,
            capture_output=True,
            text=True,
            timeout=60
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        return output.strip() if output.strip() else "[Command completed with no output]"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except ValueError as e:
        return f"[ParseError] Invalid command syntax: {str(e)}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
