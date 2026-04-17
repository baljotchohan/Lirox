"""Lirox v1.1 — Central Configuration"""
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
    APP_VERSION = "1.0.0"  # fallback when running from source without install
_REPO_ROOT   = Path(__file__).resolve().parent.parent
PROJECT_ROOT = str(_REPO_ROOT)
DATA_DIR     = str(_REPO_ROOT / "data")
MEMORY_DIR   = str(_REPO_ROOT / "data" / "memory")
SESSIONS_DIR = str(_REPO_ROOT / "data" / "sessions")
OUTPUTS_DIR  = str(_REPO_ROOT / "outputs")

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
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY")
NVIDIA_API_KEY     = os.getenv("NVIDIA_API_KEY")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY")

LOCAL_LLM_ENABLED = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"
OLLAMA_ENDPOINT   = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3")

DEFAULT_MODEL        = os.getenv("DEFAULT_MODEL", "groq")
MEMORY_LIMIT         = int(os.getenv("MEMORY_LIMIT", "100"))
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "30"))
THINKING_ENABLED     = os.getenv("THINKING_ENABLED", "true").lower() == "true"
LLM_TIMEOUT          = int(os.getenv("LLM_TIMEOUT", "90"))
PLAN_CONFIRM         = True
MAX_RETRIES          = 3

MAX_LLM_PROMPT_CHARS    = 16000
MAX_TOOL_RESULT_CHARS   = 4000
MAX_MEMORY_ENTRY_CHARS  = 800
MAX_CONTEXT_CHARS       = 6000
MAX_SEARCH_RESULT_CHARS = 10000
THINKING_DEPTH          = "complex"

ALLOWED_COMMANDS = [
    "ls", "pwd", "find", "which", "whoami", "file", "wc", "head", "tail", "du", "df",
    "mkdir", "touch", "cat", "cp", "mv", "rm", "echo", "tee", "python", "python3",
    "node", "npx", "git", "cargo", "go", "rustc", "gcc", "make", "curl", "wget",
    "ping", "grep", "awk", "sed", "sort", "uniq", "tr", "cut", "xargs", "uname",
    "date", "cal", "env", "tar", "zip", "unzip", "gzip", "docker", "pytest",
    "black", "flake8", "mypy", "eslint", "shasum", "open", "xdg-open", "osascript",
    "xclip", "code", "vim", "nano", "less", "more", "diff", "patch", "pip", "pip3",
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
    os.path.join(_HOME, "cpp"),
    os.path.join(_HOME, "python"),
    os.path.join(_HOME, "js"),
    os.path.join(_HOME, "go"),
    os.path.join(_HOME, "rust"),
    "/tmp",
]
SAFE_DIRS_RESOLVED = [os.path.realpath(d) for d in SAFE_DIRS]

PROTECTED_PATHS = [
    "/etc", "/sys", "/proc", "/boot", "/dev",
    "/usr/bin", "/usr/lib", "/usr/sbin",
    "/System", "/Library/System", "/private",
    "C:\\Windows", "C:\\Program Files",
]

PARALLEL_MAX_WORKERS = 4
RETRY_BACKOFF        = 1.0

MIND_DIR          = str(_REPO_ROOT / "data" / "mind")
MIND_SOUL_FILE    = str(_REPO_ROOT / "data" / "mind" / "soul.json")
MIND_LEARN_FILE   = str(_REPO_ROOT / "data" / "mind" / "learnings.json")
MIND_PATTERN_FILE = str(_REPO_ROOT / "data" / "mind" / "patterns.json")
MIND_SKILLS_DIR   = str(_REPO_ROOT / "data" / "mind" / "skills")
MIND_AGENTS_DIR   = str(_REPO_ROOT / "data" / "mind" / "agents")
PATCHES_DIR       = str(_REPO_ROOT / "data" / "pending_patches")

for _d in [OUTPUTS_DIR, DATA_DIR, MEMORY_DIR, SESSIONS_DIR,
           str(Path(MEMORY_DIR) / "daily"),
           MIND_DIR, MIND_SKILLS_DIR, MIND_AGENTS_DIR, PATCHES_DIR]:
    os.makedirs(_d, exist_ok=True)

# ── v1.1 additions ──────────────────────────────────────────────────────

# Directories where writes are considered "self-modification".
# Writes inside these roots require LIROX_ALLOW_SELF_MOD=1 to proceed.
SELF_MOD_ROOTS = [
    PROJECT_ROOT,
]


def is_self_modification(path: str) -> bool:
    """True if `path` resolves to a location inside the Lirox source tree.

    Used by the verified file layer to gate writes/deletes/patches that
    would modify Lirox itself. Reads are always allowed.
    """
    try:
        resolved = str(Path(path).expanduser().resolve())
    except Exception:
        return False
    for root in SELF_MOD_ROOTS:
        try:
            root_r = str(Path(root).resolve())
        except Exception:
            continue
        if resolved == root_r or resolved.startswith(root_r + os.sep):
            return True
    return False
