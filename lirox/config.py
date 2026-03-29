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
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# Default settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai")
MEMORY_LIMIT = 10
SYSTEM_PROMPT = "You are Lirox, a helpful and concise local AI agent. You can execute terminal commands and plan tasks. If the user says hello, just greet them normally and do not try to troubleshoot API keys unless explicitly asked."

# Safety settings
ALLOWED_COMMANDS = ["ls", "mkdir", "python", "pip", "npm", "echo", "touch", "cat"]
BLOCK_COMMANDS = ["rm -rf", "shutdown", "reboot", "mv", "rm"] # Minimal blocking, user can override
