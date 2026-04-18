"""Lirox v3.0 — Central Configuration"""
import os
import stat
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    import sys
    print("\n[!] pip install python-dotenv\n")
    sys.exit(1)

APP_VERSION = "3.0.0"  # Unified to v3.0 Master Rebuild

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

# ── API Keys ──
# Raw env-var reads kept for backward compatibility with code that accesses
# these module-level names directly.  New code should prefer
# lirox.utils.secure_keys.get_api_key() which masks values in logs.
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

# ── Agent Behavior ──
DEFAULT_MODEL        = os.getenv("DEFAULT_MODEL", "groq")
MEMORY_LIMIT         = int(os.getenv("MEMORY_LIMIT", "100"))
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "30"))
LLM_TIMEOUT          = int(os.getenv("LLM_TIMEOUT", "90"))
SHELL_TIMEOUT        = int(os.getenv("SHELL_TIMEOUT", "60"))
MAX_RETRIES          = 3

MAX_LLM_PROMPT_CHARS    = 16000
MAX_TOOL_RESULT_CHARS   = 4000
MAX_MEMORY_ENTRY_CHARS  = 800
MAX_CONTEXT_CHARS       = 6000
MAX_SEARCH_RESULT_CHARS = 10000

# ── Workspace (where agent reads/writes files for the user) ──
# This is the folder the agent operates in — like Claude Code / Gemini CLI
WORKSPACE_DIR = os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop"))

# ── Shell Safety ──
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
    PROJECT_ROOT, OUTPUTS_DIR, DATA_DIR, WORKSPACE_DIR,
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

# ── Mind / Learnings ──
MIND_DIR          = str(_REPO_ROOT / "data" / "mind")
MIND_SOUL_FILE    = str(_REPO_ROOT / "data" / "mind" / "soul.json")
MIND_LEARN_FILE   = str(_REPO_ROOT / "data" / "mind" / "learnings.json")

# ── Self-awareness: path to own source code ──
LIROX_SOURCE_DIR  = str(_REPO_ROOT / "lirox")

# ── Auto-training ──
AUTO_TRAIN_ENABLED          = os.getenv("AUTO_TRAIN_ENABLED", "true").lower() == "true"
AUTO_TRAIN_AFTER_MESSAGES   = int(os.getenv("AUTO_TRAIN_AFTER_MESSAGES", "10"))

# ── Directory creation ──
def _make_dir_safe(path: str) -> None:
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
        info = os.stat(path)
        if not (info.st_mode & stat.S_IWUSR):
            raise PermissionError(f"Directory not writable: {path}")
    except PermissionError as exc:
        raise PermissionError(
            f"[Lirox] Cannot access directory: {path}\n  {exc}"
        ) from exc
    except OSError as exc:
        raise OSError(
            f"[Lirox] Failed to create directory: {path}\n  {exc}"
        ) from exc

for _d in [OUTPUTS_DIR, DATA_DIR, MEMORY_DIR, SESSIONS_DIR,
           str(Path(MEMORY_DIR) / "daily"), MIND_DIR]:
    _make_dir_safe(_d)

def is_self_modification(path: str) -> bool:
    try:
        p = str(Path(path).resolve())
        return p.startswith(str(Path(LIROX_SOURCE_DIR).resolve()))
    except Exception:
        return False
