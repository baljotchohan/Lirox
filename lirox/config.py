"""Lirox v2.0.0 — Central Configuration"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    import sys
    print("\n[!] pip install python-dotenv\n")
    sys.exit(1)

try:
    from importlib.metadata import version as _pkg_version
    APP_VERSION = _pkg_version("lirox")
except Exception:
    APP_VERSION = "2.0.0"

_REPO_ROOT   = Path(__file__).resolve().parent.parent
PROJECT_ROOT = str(_REPO_ROOT)
DATA_DIR     = str(_REPO_ROOT / "data")
MEMORY_DIR   = str(_REPO_ROOT / "data" / "memory")
SESSIONS_DIR = str(_REPO_ROOT / "data" / "sessions")
OUTPUTS_DIR  = str(_REPO_ROOT / "outputs")
SKILLS_DIR   = str(_REPO_ROOT / "data" / "skills")
AGENTS_DIR   = str(_REPO_ROOT / "data" / "agents")
LOGS_DIR     = str(_REPO_ROOT / "data" / "logs")
BACKUPS_DIR  = str(_REPO_ROOT / "data" / "backups")

for _ef in [_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"]:
    if _ef.exists():
        load_dotenv(str(_ef))
        break
else:
    load_dotenv()

OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")

LOCAL_LLM_ENABLED = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"
OLLAMA_ENDPOINT   = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3")

DEFAULT_MODEL        = os.getenv("DEFAULT_MODEL", "groq")
MEMORY_LIMIT         = int(os.getenv("MEMORY_LIMIT", "100"))
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))
LLM_TIMEOUT          = int(os.getenv("LLM_TIMEOUT", "90"))

MAX_LLM_PROMPT_CHARS    = 16000
MAX_TOOL_RESULT_CHARS   = 4000
MAX_CONTEXT_CHARS       = 6000

ALLOWED_COMMANDS = [
    "ls", "pwd", "find", "which", "whoami", "file", "wc", "head", "tail", "du", "df",
    "mkdir", "touch", "cat", "cp", "mv", "rm", "echo", "tee", "python", "python3",
    "node", "npx", "git", "cargo", "go", "rustc", "gcc", "make", "curl", "wget",
    "ping", "grep", "awk", "sed", "sort", "uniq", "tr", "cut", "xargs", "uname",
    "date", "cal", "env", "tar", "zip", "unzip", "gzip", "docker", "pytest",
    "black", "flake8", "mypy", "eslint", "shasum", "open", "xdg-open",
    "xclip", "code", "vim", "nano", "less", "more", "diff", "pip", "pip3",
    "brew", "apt", "npm", "yarn",
]

BLOCK_PATTERNS = [
    "rm -rf /", "rm -rf ~", "shutdown", "reboot", "mv /", "rm /",
    "chmod 777", "sudo rm", "dd if", "mkfs", ":(){ :|:& };:", "> /dev",
    "format c:", "del /f /s", "deltree", "fdisk",
]

_HOME = str(Path.home())
SAFE_DIRS = [
    PROJECT_ROOT, OUTPUTS_DIR, DATA_DIR,
    _HOME,
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Downloads"),
    os.path.join(_HOME, "Projects"),
    os.path.join(_HOME, "code"),
    os.path.join(_HOME, "dev"),
    os.path.join(_HOME, "workspace"),
    os.path.join(_HOME, "repos"),
    os.path.join(_HOME, "src"),
    "/tmp",
]
SAFE_DIRS_RESOLVED = [os.path.realpath(d) for d in SAFE_DIRS]

PROTECTED_PATHS = [
    "/etc", "/sys", "/proc", "/boot", "/dev",
    "/usr/bin", "/usr/lib", "/usr/sbin",
    "/System", "/Library/System", "/private",
    "C:\\Windows", "C:\\Program Files",
]

for _d in [
    OUTPUTS_DIR, DATA_DIR, MEMORY_DIR, SESSIONS_DIR,
    SKILLS_DIR, AGENTS_DIR, LOGS_DIR, BACKUPS_DIR,
    str(Path(MEMORY_DIR) / "daily"),
]:
    os.makedirs(_d, exist_ok=True)
