"""Lirox v1.1 — Central Configuration"""
import os
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    # Graceful fallback: define a no-op stub so the module still loads.
    # Health checks will surface the missing dependency instead of crashing.
    def load_dotenv(*a, **kw):
        pass

APP_VERSION = "1.0.0"

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
LLM_TIMEOUT          = int(os.getenv("LIROX_LLM_TIMEOUT", os.getenv("LLM_TIMEOUT", "90")))
SHELL_TIMEOUT        = int(os.getenv("LIROX_SHELL_TIMEOUT", os.getenv("SHELL_TIMEOUT", "60")))
FILE_TIMEOUT         = int(os.getenv("LIROX_FILE_TIMEOUT", "30"))
MAX_RETRIES          = 3

MAX_LLM_PROMPT_CHARS    = 16000  # ~4000 tokens: keeps prompts within typical model context windows
MAX_TOOL_RESULT_CHARS   = 4000   # ~1000 tokens: tool results injected back into the LLM context
MAX_MEMORY_ENTRY_CHARS  = 800    # ~200 tokens: per-message budget in the memory buffer
MAX_CONTEXT_CHARS       = 6000   # ~1500 tokens: recent-context window injected into each prompt
MAX_SEARCH_RESULT_CHARS = 10000  # ~2500 tokens: web/search results before summarisation

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
# FIX-14: Removed _HOME itself — only specific subdirs are allowed
# NOTE: /tmp is intentionally excluded — it is world-writable and susceptible
#       to symlink attacks.  Sandbox any /tmp usage outside SAFE_DIRS checks.
SAFE_DIRS = [
    PROJECT_ROOT, OUTPUTS_DIR, DATA_DIR, WORKSPACE_DIR,
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Downloads"),
    os.path.join(_HOME, "Projects"),
    os.path.join(_HOME, "code"),
    os.path.join(_HOME, "dev"),
    os.path.join(_HOME, "workspace"),
    os.path.join(_HOME, "repos"),
    os.path.join(_HOME, "src"),
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

LIROX_SOURCE_DIR  = str(_REPO_ROOT / "lirox")

AUTO_TRAIN_ENABLED          = os.getenv("AUTO_TRAIN_ENABLED", "true").lower() == "true"
AUTO_TRAIN_AFTER_MESSAGES   = int(os.getenv("AUTO_TRAIN_AFTER_MESSAGES", "10"))

# ── Thinking / Reasoning ──
THINKING_ENABLED = os.getenv("LIROX_THINKING", "true").lower() != "false"


# FIX-04: Deferred directory creation — called from main(), not at import
_dirs_initialized = False

def ensure_directories():
    """Create data directories. Called once from main(), not at import time."""
    global _dirs_initialized
    if _dirs_initialized:
        return
    for d in [OUTPUTS_DIR, DATA_DIR, MEMORY_DIR, SESSIONS_DIR,
              str(Path(MEMORY_DIR) / "daily"), MIND_DIR]:
        try:
            os.makedirs(d, mode=0o700, exist_ok=True)
        except OSError as exc:
            import logging
            logging.getLogger("lirox.config").warning(f"Cannot create {d}: {exc}")
    _dirs_initialized = True


def is_self_modification(path: str) -> bool:
    try:
        p = str(Path(path).resolve())
        return p.startswith(str(Path(LIROX_SOURCE_DIR).resolve()))
    except Exception:
        return False

# ── Unicorn Strategy Pillars ──
PILLAR_1_LEARNING = {
    'enabled': True,
    'track_preferences': True,
    'apply_learned_style': True,
    'show_improvement': True,
    'learning_dashboard': True
}

PILLAR_2_SECURITY = {
    'agent_identity': True,
    'kill_switch': True,
    'rate_limiting': True,
    'behavioral_monitoring': True,
    'audit_trail': True
}

PILLAR_3_MULTI_AGENT = {
    'coordinator_agent': True,
    'code_agent': True,
    'test_agent': True,
    'research_agent': True,
    'doc_agent': True,
    'enabled_by_default': True
}

PILLAR_4_TESTING = {
    'red_team_framework': True,
    'owasp_compliance': True,
    'safe_to_deploy_decision': True,
    'regression_testing': True
}

PILLAR_5_MARKETPLACE = {
    'agent_registry': True,
    'code_signing': True,
    'monetization': True,
    'community_agents': True
}
