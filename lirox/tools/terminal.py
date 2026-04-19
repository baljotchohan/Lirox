"""
Lirox v1.1 — Terminal Tool (hardened)

Safe command execution with:
- Expanded allowlist for common dev/system tools
- Smart injection detection that allows safe chaining (;) but blocks dangerous patterns
- Block-list for destructive commands
- Timeout protection
"""

import subprocess
import os
import sys
import shlex
import re
from lirox.config import ALLOWED_COMMANDS, BLOCK_PATTERNS
from lirox.utils.regex_cache import SHELL_VAR_ASSIGN, SHELL_CHAIN

# Dangerous injection patterns — only truly dangerous ones
# We now allow safe chaining like "&&" and ";" for multi-step commands,
# but block patterns that could be used for data exfiltration or code injection
INJECTION_PATTERNS = [
    "$(", "`",           # Command substitution (arbitrary code execution)
    "eval ", "exec(",    # Code injection
    ">/dev",             # Device writes (with or without space before >)
    "| base64",          # Exfiltration
    "| curl",            # Exfiltration
    "|curl",             # Exfiltration (no space)
    "| wget",            # Exfiltration
    "|wget",             # Exfiltration (no space)
    "&>/",               # Combined stdout/stderr redirect to arbitrary path
    "tee /",             # Writing to arbitrary paths via tee
    "/dev/tcp/",         # Bash TCP redirection (reverse shells)
    "/dev/udp/",         # Bash UDP redirection (reverse shells)
]

# SECURITY-02: Additional argument-level validation for inherently dangerous commands.
# These commands are allowed in the allowlist but must not be used with unsafe arguments.

# rm: block recursive+force flag combos (joined or separate) targeting broad paths.
# Matches: rm -rf /, rm -fr ~, rm -r -f *, rm -f -r .. etc.
_RM_DANGEROUS = re.compile(
    r'\brm\b'
    r'(?=.*\s-[a-z]*r[a-z]*)(?=.*\s-[a-z]*f[a-z]*)'  # has both -r and -f (any order/form)
    r'.*\s(\/|~|\*|\.\.)',
    re.IGNORECASE,
)
# find: block -exec which can execute arbitrary commands
_FIND_EXEC = re.compile(r'\bfind\b.*\s-exec\b', re.IGNORECASE)
# python/python3: block -c (inline code) which bypasses script-path checks
_PYTHON_INLINE = re.compile(r'\bpython3?\b\s+-c\b', re.IGNORECASE)


def _check_dangerous_args(cmd: str) -> tuple:
    """Additional argument-level safety checks for high-risk allowed commands.

    Returns (ok: bool, reason: str).
    """
    if _RM_DANGEROUS.search(cmd):
        return False, "rm with recursive+force flags targeting broad paths is blocked"
    if _FIND_EXEC.search(cmd):
        return False, "find -exec is blocked (use find + xargs if needed)"
    if _PYTHON_INLINE.search(cmd):
        return False, "python -c inline code execution is blocked"
    return True, "ok"


def is_safe(cmd):
    """
    Multi-layer safety check:
    1. Block dangerous commands and injection patterns
    2. Check injection patterns
    3. Argument-level validation for high-risk allowed commands (SECURITY-02)
    4. Check that every command in a chain/pipe is on the allowlist
    """
    cmd_lower = cmd.lower().strip()

    # 1. Check blocklist (exact dangerous patterns)
    for blocked in BLOCK_PATTERNS:
        if blocked in cmd_lower:
            return False, f"Blocked command/flag: '{blocked}'"

    # 2. Check injection patterns — case-insensitive (FIX-05)
    cmd_for_injection = cmd.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern.lower() in cmd_for_injection:
            return False, f"Blocked injection pattern: '{pattern}'"

    # 3. SECURITY-02: Argument-level checks for dangerous but allowed commands
    safe, reason = _check_dangerous_args(cmd)
    if not safe:
        return False, reason

    # 4. Comprehensive Chain/Pipe Parsing
    # We split by all shell delimiters to ensure NO command escapes validation
    # Split by: &&, ||, ;, | (with optional surrounding whitespace)
    sub_commands = SHELL_CHAIN.split(cmd)

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
                if SHELL_VAR_ASSIGN.match(p):
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
    from lirox.config import SHELL_TIMEOUT
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
            timeout=SHELL_TIMEOUT
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        return output.strip() if output.strip() else "[Command completed with no output]"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except ValueError as e:
        return f"[ParseError] Invalid command syntax: {str(e)}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
