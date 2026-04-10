"""Lirox v1.0.0 — Streaming Response Engine"""
from __future__ import annotations
import re
import time
from typing import Generator


class StreamingResponse:
    """Stream responses. Code blocks yielded atomically — never split or truncated."""

    def stream_in_paragraphs(self, text: str, delay: float = 0.0) -> Generator[str, None, None]:
        """
        Split text into natural chunks for display.
        Code blocks (``` ... ```) are always yielded as a single atomic unit.
        Regular prose is split on blank lines.
        """
        parts = re.split(r"(```[\s\S]*?```)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("```"):
                yield part
                if delay > 0:
                    time.sleep(delay)
            else:
                paragraphs = part.split("\n\n")
                for idx, para in enumerate(paragraphs):
                    suffix = "\n\n" if idx < len(paragraphs) - 1 else ""
                    yield para + suffix
                    if delay > 0 and para.strip():
                        time.sleep(delay)

    def stream_with_typing(self, text: str, delay: float = 0.008,
                           chunk_size: int = 3) -> Generator[str, None, None]:
        for i in range(0, len(text), chunk_size):
            yield text[i: i + chunk_size]
            if delay > 0:
                time.sleep(delay)
