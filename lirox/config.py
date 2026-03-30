import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env or .env.local
for env_file in ['.env', '.env.local']:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        break
else:
    load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Default settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai")
MEMORY_LIMIT = 20  # Increased from 10

# Terminal safety — expanded allowlist
ALLOWED_COMMANDS = [
    # Navigation & listing
    "ls", "pwd", "find", "which", "whoami", "file", "wc", "head", "tail", "du", "df",
    # File operations (safe)
    "mkdir", "touch", "cat", "cp", "mv", "rm", "echo", "tee",
    # Development tools
    "python", "python3", "pip", "pip3", "npm", "npx", "node", "yarn",
    "git", "cargo", "go", "rustc", "gcc", "make",
    # Network & fetching
    "curl", "wget",
    # Text processing
    "grep", "awk", "sed", "sort", "uniq", "tr", "cut", "xargs",
    # System info
    "uname", "date", "cal", "env", "printenv", "sleep",
    # Archive
    "tar", "zip", "unzip", "gzip",
]

BLOCK_COMMANDS = [
    "rm -rf /", "rm -rf ~", "shutdown", "reboot", "mv /", "rm /",
    "chmod 777", "sudo rm", "dd if", "mkfs", ":(){ :|:& };:",
    "format", "fdisk", "> /dev"
]

# ─── v0.3 Settings ────────────────────────────────────────────────────────────

# Project Root (anchored to the lirox package directory)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Planning & Execution
PLAN_CONFIRM = True          # Ask user before executing plans
MAX_RETRIES = 3              # Retry limit for failed steps
RETRY_BACKOFF = 1.0          # Backoff multiplier (seconds)

# File I/O safety — expanded to user-accessible directories
# Resolves ~/ to actual home path at load time
_HOME = str(Path.home())
SAFE_DIRS = [
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "outputs"),
    os.path.join(PROJECT_ROOT, "data"),
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Downloads"),
]

# Browser
BROWSER_TIMEOUT = 10         # Web request timeout (seconds)
