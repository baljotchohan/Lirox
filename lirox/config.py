"""Lirox v2.0 — Central Configuration"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    import sys
    print("\n[!] pip install python-dotenv\n")
    sys.exit(1)

APP_VERSION = "2.0.0"
_REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = str(_REPO_ROOT)
DATA_DIR = str(_REPO_ROOT / "data")
MEMORY_DIR = str(_REPO_ROOT / "data" / "memory")
OUTPUTS_DIR = str(_REPO_ROOT / "outputs")

for ef in [_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"]:
    if ef.exists():
        load_dotenv(str(ef))
        break
else:
    load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
FINANCIAL_DATASETS_KEY = os.getenv("FINANCIAL_DATASETS_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "groq")
MEMORY_LIMIT = int(os.getenv("MEMORY_LIMIT", "100"))
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "15"))
THINKING_ENABLED = os.getenv("THINKING_ENABLED", "true").lower() == "true"
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
PLAN_CONFIRM = True
MAX_RETRIES = 3
CONTEXT_MAX_CHARS = 4000

# Terminal Safety
ALLOWED_COMMANDS = [
    "ls", "pwd", "find", "which", "whoami", "file", "wc", "head", "tail", "du", "df",
    "mkdir", "touch", "cat", "cp", "mv", "rm", "echo", "tee", "python", "python3",
    "node", "npx", "git", "cargo", "go", "rustc", "gcc", "make", "curl", "wget",
    "ping", "grep", "awk", "sed", "sort", "uniq", "tr", "cut", "xargs", "uname",
    "date", "cal", "env", "tar", "zip", "unzip", "gzip", "pip", "pip3", "npm",
    "yarn", "docker", "pytest", "black", "flake8", "mypy", "eslint", "shasum",
]
BLOCK_PATTERNS = [
    "rm -rf /", "rm -rf ~", "shutdown", "reboot", "mv /", "rm /",
    "chmod 777", "sudo rm", "dd if", "mkfs", ":(){ :|:& };:", "> /dev",
]

# Browser
BROWSER_CONFIG = {
    "cdp_endpoint": os.getenv("CDP_ENDPOINT", "http://localhost:9222"),
    "timeout": int(os.getenv("BROWSER_TIMEOUT", "30")),
    "headless": True,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
BROWSER_TIMEOUT = 15

# File Safety
_HOME = str(Path.home())
SAFE_DIRS = [
    PROJECT_ROOT, OUTPUTS_DIR, DATA_DIR,
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Downloads"),
]
SAFE_DIRS_RESOLVED = [os.path.realpath(d) for d in SAFE_DIRS]
PARALLEL_MAX_WORKERS = 4
RETRY_BACKOFF = 1.0

for d in [OUTPUTS_DIR, DATA_DIR, MEMORY_DIR, str(Path(MEMORY_DIR) / "daily")]:
    os.makedirs(d, exist_ok=True)
