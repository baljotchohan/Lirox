"""
Lirox v0.8.5 — Central Configuration

All paths are anchored to the REPO ROOT (two levels above this file),
so Lirox works correctly regardless of which directory it is launched from.
"""

import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    import sys
    print("\n[!] ERROR: 'python-dotenv' is not installed.")
    print("    To fix, run:  python -m pip install python-dotenv")
    print("    If you already installed it, use: python -m lirox.main\n")
    sys.exit(1)

# ─── Version ─────────────────────────────────────────────────────────────────
APP_VERSION = "1.0.0"

# ─── Path Anchoring ───────────────────────────────────────────────────────────
# Repo root is always 2 levels above this file:
#   lirox/config.py → lirox/ → Lirox/  (repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Keep _PROJECT_ROOT_DIR for backward compat with server/routes.py
_PROJECT_ROOT_DIR = _REPO_ROOT

# Public constants
PROJECT_ROOT = str(_REPO_ROOT)         # repo root as string

# Data directories — always inside repo root
DATA_DIR     = str(_REPO_ROOT / "data")
OUTPUTS_DIR  = str(_REPO_ROOT / "outputs")

# ─── .env Loading ────────────────────────────────────────────────────────────
for env_file in [_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"]:
    if env_file.exists():
        load_dotenv(str(env_file))
        break
else:
    load_dotenv()

# ─── API Keys ────────────────────────────────────────────────────────────────
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY")
NVIDIA_API_KEY     = os.getenv("NVIDIA_API_KEY")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")

# ─── Default Settings ────────────────────────────────────────────────────────
DEFAULT_MODEL  = os.getenv("DEFAULT_MODEL", "groq")
MEMORY_LIMIT   = int(os.getenv("MEMORY_LIMIT", "20"))

# ─── Terminal Safety — Expanded Allowlist ────────────────────────────────────
ALLOWED_COMMANDS = [
    # Navigation & listing
    "ls", "pwd", "find", "which", "whoami", "file", "wc", "head", "tail", "du", "df",
    # File operations (safe)
    "mkdir", "touch", "cat", "cp", "mv", "rm", "echo", "tee", "shasum", "md5",
    # Development tools (Execution only, no installs)
    "python", "python3", "node", "npx", "yarn",
    "git", "cargo", "go", "rustc", "gcc", "make",
    # Network & fetching
    "curl", "wget", "ping",
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

# ─── v0.5 Settings ───────────────────────────────────────────────────────────

# Planning & Execution
PLAN_CONFIRM         = True    # Ask user before executing plans
MAX_RETRIES          = 3       # Retry limit for failed steps
RETRY_BACKOFF        = 1.0     # Backoff multiplier (seconds)

# Context window for step chaining (chars)
CONTEXT_MAX_CHARS    = 4000

# Parallel execution: max workers for concurrent steps
PARALLEL_MAX_WORKERS = 4

# File I/O safety — expanded to user-accessible directories
_HOME = str(Path.home())
SAFE_DIRS = [
    PROJECT_ROOT,
    OUTPUTS_DIR,
    DATA_DIR,
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Downloads"),
]

# [FIX #1] Resolve symlinks to prevent path traversal
SAFE_DIRS_RESOLVED = [os.path.realpath(d) for d in SAFE_DIRS]

# Browser (basic requests-based)
BROWSER_TIMEOUT = 15    # Web request timeout (seconds)

# LLM
LLM_TIMEOUT = 60        # LLM API call timeout (seconds)

# ─── Headless Browser Config (v0.8.5 — Lightpanda) ────────────────────────────

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BROWSER_CONFIG = {
    "lightpanda_path": os.getenv("LIGHTPANDA_PATH", str(_REPO_ROOT / "lightpanda")),
    "port": int(os.getenv("BROWSER_PORT", 9222)),
    "max_instances": int(os.getenv("BROWSER_MAX_INSTANCES", 5)),
    "timeout": int(os.getenv("BROWSER_TIMEOUT", 30)),
    "headless": os.getenv("BROWSER_HEADLESS", "true").lower() == "true",
    "disable_images": os.getenv("BROWSER_DISABLE_IMAGES", "false").lower() == "true",
    "user_agent": os.getenv("BROWSER_USER_AGENT", _DEFAULT_USER_AGENT),
    "rate_limits": {
        "per_domain": int(os.getenv("BROWSER_RATE_LIMIT_PER_DOMAIN", 10)),
        "global": int(os.getenv("BROWSER_RATE_LIMIT_GLOBAL", 100)),
    },
    "blocklist": os.getenv(
        "BROWSER_BLOCKLIST", "localhost,127.0.0.1,169.254.169.254"
    ).split(","),
    "cookie_dir": os.getenv("BROWSER_COOKIE_DIR", str(_REPO_ROOT / "data" / "browser_cookies")),
}

# Ensure outputs/ and data/ exist
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
