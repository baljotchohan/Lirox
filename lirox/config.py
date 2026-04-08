"""Lirox v3.0 — Central Configuration"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    import sys
    print("\n[!] pip install python-dotenv\n")
    sys.exit(1)

APP_VERSION = "1.0.0"
_REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = str(_REPO_ROOT)
DATA_DIR = str(_REPO_ROOT / "data")
MEMORY_DIR = str(_REPO_ROOT / "data" / "memory")
SESSIONS_DIR = str(_REPO_ROOT / "data" / "sessions")
OUTPUTS_DIR = str(_REPO_ROOT / "outputs")

for ef in [_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"]:
    if ef.exists():
        load_dotenv(str(ef))
        break
else:
    load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY")
NVIDIA_API_KEY     = os.getenv("NVIDIA_API_KEY")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY")

# ── Local LLM ─────────────────────────────────────────────────────────────────
LOCAL_LLM_ENABLED = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"
OLLAMA_ENDPOINT   = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "gemma4")

# ── Core Settings ─────────────────────────────────────────────────────────────
DEFAULT_MODEL        = os.getenv("DEFAULT_MODEL", "groq")
MEMORY_LIMIT         = int(os.getenv("MEMORY_LIMIT", "100"))
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "30"))
THINKING_ENABLED     = os.getenv("THINKING_ENABLED", "true").lower() == "true"
LLM_TIMEOUT          = int(os.getenv("LLM_TIMEOUT", "60"))
PLAN_CONFIRM         = True
MAX_RETRIES          = 3
CONTEXT_MAX_CHARS    = 4000

# ── Always-on thinking ────────────────────────────────────────────────────────
THINKING_DEPTH = "complex"

# ── Content limits ────────────────────────────────────────────────────────────
MAX_LLM_PROMPT_CHARS    = 8000
MAX_TOOL_RESULT_CHARS   = 2000
MAX_MEMORY_ENTRY_CHARS  = 500
MAX_CONTEXT_CHARS       = 4000
MAX_SEARCH_RESULT_CHARS = 10000

# ── Desktop Control ───────────────────────────────────────────────────────────
# Set DESKTOP_ENABLED=true in .env to unlock full OS control
DESKTOP_ENABLED = os.getenv("DESKTOP_ENABLED", "false").lower() == "true"
# Max steps before agent stops and asks for guidance
DESKTOP_MAX_STEPS = int(os.getenv("DESKTOP_MAX_STEPS", "40"))
# Delay between desktop actions (seconds) — give UI time to respond
DESKTOP_ACTION_DELAY = float(os.getenv("DESKTOP_ACTION_DELAY", "0.6"))

# ── Terminal Safety (commands the agent CAN run) ──────────────────────────────
ALLOWED_COMMANDS = [
    "ls", "pwd", "find", "which", "whoami", "file", "wc", "head", "tail", "du", "df",
    "mkdir", "touch", "cat", "cp", "mv", "rm", "echo", "tee", "python", "python3",
    "node", "npx", "git", "cargo", "go", "rustc", "gcc", "make", "curl", "wget",
    "ping", "grep", "awk", "sed", "sort", "uniq", "tr", "cut", "xargs", "uname",
    "date", "cal", "env", "tar", "zip", "unzip", "gzip", "docker", "pytest",
    "black", "flake8", "mypy", "eslint", "shasum", "open", "xdg-open", "osascript",
    "screencapture", "scrot", "xdotool", "wmctrl", "xwininfo", "pbcopy", "pbpaste",
    "xclip", "code", "vim", "nano", "less", "more", "diff", "patch",
]

# ── Absolute block patterns — NEVER execute these ────────────────────────────
BLOCK_PATTERNS = [
    "rm -rf /", "rm -rf ~", "shutdown", "reboot", "mv /", "rm /",
    "chmod 777", "sudo rm", "dd if", "mkfs", ":(){ :|:& };:", "> /dev",
    "format c:", "del /f /s", "deltree", "fdisk",
]

# ── File Safety — agent can only read/write these dirs ───────────────────────
_HOME = str(Path.home())
SAFE_DIRS = [
    PROJECT_ROOT,
    OUTPUTS_DIR,
    DATA_DIR,
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Downloads"),
    os.path.join(_HOME, "Projects"),
    os.path.join(_HOME, "code"),
    os.path.join(_HOME, "dev"),
]
SAFE_DIRS_RESOLVED = [os.path.realpath(d) for d in SAFE_DIRS]

# ── System files the agent CANNOT touch (extra safety layer) ─────────────────
PROTECTED_PATHS = [
    "/etc", "/sys", "/proc", "/boot", "/dev",
    "/usr/bin", "/usr/lib", "/usr/sbin",
    "/System", "/Library/System", "/private",
    "C:\\Windows", "C:\\Program Files",
]

PARALLEL_MAX_WORKERS = 4
RETRY_BACKOFF        = 1.0

# ── Mind Agent Paths ──────────────────────────────────────────────────────────
MIND_DIR         = str(_REPO_ROOT / "data" / "mind")
MIND_SOUL_FILE   = str(_REPO_ROOT / "data" / "mind" / "soul.json")
MIND_LEARN_FILE  = str(_REPO_ROOT / "data" / "mind" / "learnings.json")
MIND_PATTERN_FILE= str(_REPO_ROOT / "data" / "mind" / "patterns.json")
MIND_SKILLS_DIR  = str(_REPO_ROOT / "data" / "mind" / "skills")
MIND_AGENTS_DIR  = str(_REPO_ROOT / "data" / "mind" / "agents")

# ── Ensure directories exist ──────────────────────────────────────────────────
for d in [OUTPUTS_DIR, DATA_DIR, MEMORY_DIR, SESSIONS_DIR,
          str(Path(MEMORY_DIR) / "daily"),
          MIND_DIR, MIND_SKILLS_DIR, MIND_AGENTS_DIR]:
    os.makedirs(d, exist_ok=True)
