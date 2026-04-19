"""Lirox v3.0 — Streaming Response Engine survival_prompt"""
from __future__ import annotations
import re
import time
from typing import Generator


class StreamingResponse:
    """Stream responses. Code blocks yielded atomically — never split or truncated."""

    def stream_words(self, text: str, delay: float = 0.01) -> Generator[str, None, None]:
        """
        Stream text word-by-word for a 'typing' effect.
        Code blocks are yielded atomically to avoid broken formatting.
        """
        parts = re.split(r"(```[\s\S]*?```)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("```"):
                yield part
                if delay > 0:
                    time.sleep(delay * 5)
            else:
                # Split by words but preserve whitespace
                words = re.split(r"(\s+)", part)
                for word in words:
                    if not word:
                        continue
                    yield word
                    if delay > 0:
                        # Slightly faster for whitespace
                        time.sleep(delay if word.strip() else delay * 0.5)

    def stream_with_typing(self, text: str, delay: float = 0.005,
                           chunk_size: int = 3) -> Generator[str, None, None]:
        for i in range(0, len(text), chunk_size):
            yield text[i: i + chunk_size]
            if delay > 0:
                time.sleep(delay)
