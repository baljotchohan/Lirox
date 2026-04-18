"""The canonical Memory Sync Prompt.

One prompt the user copies into any LLM (ChatGPT, Claude, Gemini).
Designed to produce JSON that Lirox can parse even when the LLM
wraps it in triple-backtick json fences or adds a preamble.
"""

MEMORY_SYNC_PROMPT = """Analyze our entire conversation history. Extract everything stable and useful for a personal AI to know about me.

Output EXACTLY one JSON object. Nothing before it, nothing after it. Wrap it in ```json fences.

Schema:
```json
{
  "facts": [
    "short factual statement about me (one per line)"
  ],
  "preferences": {
    "communication": ["how I like to be talked to"],
    "tools": ["tools I use"],
    "workflow": ["how I work"],
    "other_category": ["..."]
  },
  "dislikes": ["things I explicitly don't like"],
  "projects": [
    {"name": "Project name", "description": "one-line description"}
  ],
  "topics": ["top 10 topics I discuss most"],
  "communication_style": {
    "tone": "formal | casual | direct",
    "depth": "short | medium | deep",
    "format": "bullets | prose | mixed"
  },
  "profile": {
    "name": "my name",
    "niche": "my primary work (e.g. Developer, Founder)",
    "current_project": "what I'm working on now"
  }
}
```

Rules:
- Be concrete and specific, not generic ("Uses Python with FastAPI for APIs" not "codes").
- Do NOT invent. If unsure, omit.
- Facts under 150 chars each. Max 50 facts.
- Output the fenced JSON block and nothing else.
"""
