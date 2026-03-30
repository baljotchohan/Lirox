import os
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

# Terminal safety
ALLOWED_COMMANDS = [
    "ls", "mkdir", "python", "python3", "pip", "pip3", "npm", "node",
    "echo", "touch", "cat", "pwd", "cd", "git", "curl", "wget", "ls", "grep"
]
BLOCK_COMMANDS = [
    "rm -rf", "shutdown", "reboot", "mv /", "rm /", "chmod 777", "sudo rm", "dd if", "mkfs"
]

# ─── v0.3 Settings ────────────────────────────────────────────────────────────

# Planning & Execution
PLAN_CONFIRM = True          # Ask user before executing plans
MAX_RETRIES = 3              # Retry limit for failed steps
RETRY_BACKOFF = 1.0          # Backoff multiplier (seconds)

# File I/O safety
SAFE_DIRS = ["./", "./outputs/", "./data/"]

# Browser
BROWSER_TIMEOUT = 10         # Web request timeout (seconds)
