"""
Classifier for Lirox tasks.
Determines what kind of task a user query is.
"""

import re

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLASSIFIER — Determines what KIND of task this is
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Priority order matters. More specific patterns checked first.

SELF_SIGNALS = [
    "your code", "your source", "how do you work", "your architecture",
    "your files", "read your", "lirox code", "understand yourself",
]

MEMORY_SIGNALS = [
    "last conversation", "what did we discuss", "what do you know about me",
    "what's my name", "who am i", "who are you", "introduce yourself",
    "what have you learned", "remember when", "our history",
]

# File GENERATION — creating new document files (pdf/docx/xlsx/pptx)
_FILEGEN_PATTERN = re.compile(
    r'\b(?:create|make|generate|build|prepare|draft|write|design)\b'
    r'.*\b(?:pdf|word|docx|doc|excel|xlsx|xls|spreadsheet|'
    r'pptx?|powerpoint|presentation|slides?|report|repoty?|resume|invoice|'
    r'certificate|letter|memo|proposal|deck|document|file|paper|chart)\b',
    re.IGNORECASE,
)


# Also match reversed order: "pdf about X" or "presentation on Y"
_FILEGEN_PATTERN_REV = re.compile(
    r'\b(?:pdf|word|docx|excel|xlsx|pptx?|powerpoint|presentation|slide|deck|report|repoty?|chart)\b'
    r'.*\b(?:about|on|of|for|with|containing)\b',
    re.IGNORECASE,
)

# Code WRITING — "write me a function", "build an app in python", etc.
# Checked BEFORE shell so these go to the code-capable chat path.
_CODE_WRITE_PATTERN = re.compile(
    r'\b(?:write|create|build|implement|code|make|develop|generate)\b'
    r'.*\b(?:function|class|script|program|app|application|api|bot|'
    r'algorithm|module|library|tool|utility|server|client|parser|'
    r'scraper|crawler|cli|command.?line)\b',
    re.IGNORECASE,
)
_CODE_WRITE_PATTERN_LANG = re.compile(
    r'\b(?:write|create|build|implement|code|make|develop|generate)\b'
    r'.*\b(?:python|javascript|typescript|java|c\+\+|golang|rust|ruby|php|swift)\b',
    re.IGNORECASE,
)

SHELL_SIGNALS = [
    "run command", "execute command", "in the terminal", "in bash",
    "run python", "git status", "git commit", "git push", "git pull",
    "npm install", "pip install", "docker run", "docker build",
    "start server", "pytest ", "cargo run", "make test", "ls ",
]

WEB_SIGNALS = [
    "search for", "look up", "find information", "google", "latest news",
    "research", "find out about", "current price", "news about",
    "in the news", "what is trending", "headlines",
    # Real-time data queries — must trigger web search, not chat
    "price of", "price today", "stock price", "share price",
    "market price", "exchange rate", "conversion rate",
    "check price", "check the price", "check current",
    "weather in", "weather today", "weather forecast",
    "score of", "match score", "live score",
    "nifty", "nifty 50", "sensex", "dow jones", "nasdaq", "s&p 500",
    "bitcoin price", "crypto price", "gold price", "silver price",
    "today's", "right now", "currently",
    "what is the price", "what is the current", "what is the latest",
    "who is the current", "who is the president", "who is the ceo",
    "latest news", "recent news",
]

# File OPERATIONS — reading/writing/listing existing files
_FILE_OP_SIGNALS = [
    "read file", "write file", "edit file", "delete file",
    "save to", "open file", "file contents",
    "list files", "show files", "what files", "find files",
    "on my desktop", "in downloads", "in documents",
    "tree", "structure", "folder", "directory",
]


def _classify(query: str) -> str:
    """
    Classify query into task type.

    Priority order (highest → lowest):
      1. self / memory signals   — introspection queries
      2. web signals             — real-time / search queries  ← checked BEFORE shell
      3. file generation         — create pdf/docx/pptx/xlsx
      4. file operations         — read/list/open existing files
      5. code writing            — write/build/implement a function/script/app
      6. shell commands          — explicit terminal/run/install keywords
      7. chat                    — everything else (incl. explain/analyze/compare)
    """
    q = query.lower().strip()

    # ── 1. SELF / MEMORY ──────────────────────────────────────────────────
    if any(sig in q for sig in SELF_SIGNALS):
        return "self"
    if any(sig in q for sig in MEMORY_SIGNALS):
        return "memory"

    # ── 2. WEB SEARCH (checked BEFORE shell so "check price" never hits shell) ──
    if any(sig in q for sig in WEB_SIGNALS):
        return "web"

    # ── 3. FILE GENERATION ────────────────────────────────────────────────
    if _FILEGEN_PATTERN.search(query) or _FILEGEN_PATTERN_REV.search(query):
        return "filegen"

    # ── 4. FILE OPERATIONS ────────────────────────────────────────────────
    if any(sig in q for sig in _FILE_OP_SIGNALS):
        return "file"

    # ── 5. CODE WRITING (checked BEFORE shell) ───────────────────────────
    # "write me a Python script", "build a REST API", "implement quicksort"
    if _CODE_WRITE_PATTERN.search(query) or _CODE_WRITE_PATTERN_LANG.search(query):
        return "chat"  # routed to chat with CoT so agent writes complete code

    # ── 6. SHELL COMMANDS ─────────────────────────────────────────────────
    if any(sig in q for sig in SHELL_SIGNALS):
        return "shell"

    # ── 7. DEFAULT: CHAT ──────────────────────────────────────────────────
    return "chat"
