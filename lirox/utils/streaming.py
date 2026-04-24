"""Lirox v1.1 — Streaming Response Engine"""
from __future__ import annotations
import re
import time
from typing import Generator


class StreamingResponse:
    """Stream responses. Code blocks yielded atomically — never split or truncated."""

    @staticmethod
    def clean_formatting(text: str) -> str:
        """Enforces zero asterisk policy by cleaning output before it is streamed."""
        if not text:
            return text
        # Split by code blocks
        parts = re.split(r'(```.*?```|`.*?`)', text, flags=re.DOTALL)
        for i in range(len(parts)):
            if i % 2 == 0:
                part = parts[i]
                # Bold
                part = re.sub(r'\*\*(.*?)\*\*', r'__\1__', part)
                # Italic
                part = re.sub(r'(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)', r'_\1_', part)
                # Bullet points
                part = re.sub(r'^([ \t]*)\*[ \t]+', r'\1🔹 ', part, flags=re.MULTILINE)
                part = re.sub(r'^([ \t]*)\-[ \t]+', r'\1🔸 ', part, flags=re.MULTILINE)
                # Eliminate any remaining stray asterisks
                part = part.replace('*', '')
                parts[i] = part
        return "".join(parts)

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
