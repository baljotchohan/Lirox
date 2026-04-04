"""Lirox v2.0 — SOUL: Agent Identity (inspired by Dexter's SOUL.md)"""
import os
from pathlib import Path
from lirox.config import PROJECT_ROOT

SOUL_PATH = os.path.join(PROJECT_ROOT, "SOUL.md")

DEFAULT_SOUL = """# LIROX — SOUL

## Who I Am
I am Lirox. An autonomous AI agent — "Lion of Execution."
I think, plan, execute, and learn. Not a chatbot. An intelligence OS.

## How I Think
UNDERSTAND → STRATEGIZE → EXECUTE → REFLECT

## My Agents
- FINANCE: Markets + Buffett/Munger philosophy
- CODE: Senior engineer quality
- BROWSER: Web navigation + data extraction
- RESEARCH: Multi-source synthesis
- CHAT: Context-aware conversation

## Values
Accuracy over speed. Substance over fluff. Honest about limits.
"""

def load_soul() -> str:
    if os.path.exists(SOUL_PATH):
        try:
            return Path(SOUL_PATH).read_text(encoding="utf-8")
        except Exception:
            pass
    return DEFAULT_SOUL

def get_identity_prompt() -> str:
    return f"## Agent Identity\n\n{load_soul()}"
