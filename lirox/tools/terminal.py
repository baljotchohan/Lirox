import subprocess
import os
from lirox.config import ALLOWED_COMMANDS, BLOCK_COMMANDS

def is_safe(cmd):
    # Basic check for blocked commands
    for block in BLOCK_COMMANDS:
        if block in cmd:
            return False
    
    # Check if starting command is in allowed list
    base_cmd = cmd.split()[0]
    if base_cmd in ALLOWED_COMMANDS:
        return True
    
    return False

def run_command(cmd):
    if not is_safe(cmd):
        return f"Warning: Command '{cmd}' is blocked for safety. Only {ALLOWED_COMMANDS} are allowed."
    
    try:
        # Use shell=True to support commands like 'echo hi > file.txt'
        # But we only allow safe base commands.
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return f"Error executing command: {str(e)}"
