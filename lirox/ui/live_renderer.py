"""Lirox v1.1 — Live Renderer: smooth character-by-character terminal output"""
from __future__ import annotations
import sys
import time
from typing import Generator

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

console = Console()

# Typing speed in seconds per character (≈7 ms gives natural feel)
_CHAR_DELAY: float = 0.007


def type_text(text: str, delay: float = _CHAR_DELAY) -> None:
    """Write *text* to stdout character-by-character with *delay* seconds between chars.

    Non-code plain text only — call :func:`render_block` for code fences.
    """
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        if delay > 0:
            time.sleep(delay)


def render_block(code_fence: str) -> None:
    """Render a Markdown code block (```...```) with Rich syntax highlighting."""
    try:
        console.print(Markdown(code_fence))
    except Exception:
        console.print(escape(code_fence), soft_wrap=True)


def stream_chunks(chunks: Generator[str, None, None], delay: float = _CHAR_DELAY) -> None:
    """Consume a generator of text *chunks* and display them live.

    Code blocks are rendered atomically with syntax highlighting;
    all other text is output character-by-character.
    """
    for chunk in chunks:
        if not chunk:
            continue
        if chunk.strip().startswith("```"):
            # Flush any pending stdout before using Rich
            sys.stdout.flush()
            render_block(chunk)
        else:
            type_text(chunk, delay=delay)
    # Ensure the cursor moves to a new line after the stream ends
    sys.stdout.write("\n")
    sys.stdout.flush()
