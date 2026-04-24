"""Lirox v1.1 — Streaming Response Engine"""
from __future__ import annotations
import re
import time
from typing import Generator


class StreamingResponse:
    """Stream responses. Code blocks yielded atomically — never split or truncated."""

    @staticmethod
    def clean_formatting(text: str) -> str:
        """Enforces zero formatting char policy. Strips *, _, and # while maintaining structure."""
        if not text:
            return text
        # Split by code blocks to avoid messing with code
        parts = re.split(r'(```.*?```|`.*?`)', text, flags=re.DOTALL)
        for i in range(len(parts)):
            if i % 2 == 0:
                part = parts[i]
                
                # Replace Headers (#) with emojis. Support variable spacing.
                # Use (?m) for multiline mode to ensure ^ matches starts of lines.
                part = re.sub(r'(?m)^#{1,3}\s+(.*)$', r'🔹 \1', part)
                part = re.sub(r'(?m)^#{4,6}\s+(.*)$', r'🔸 \1', part)
                
                # Replace Bold/Italic markers (** or __) with nothing
                # Non-greedy matches to avoid over-eating text
                part = re.sub(r'\*\*(.*?)\*\*', r'\1', part)
                part = re.sub(r'__(.*?)__', r'\1', part)
                part = re.sub(r'\*(.*?)\*', r'\1', part)
                part = re.sub(r'_(.*?)_', r'\1', part)
                
                # Replace Bullet points (* or -) with emojis
                part = re.sub(r'(?m)^([ \t]*)\*[ \t]+', r'\1🔹 ', part)
                part = re.sub(r'(?m)^([ \t]*)\-[ \t]+', r'\1🔸 ', part)
                
                # Final pass: Eliminate any remaining stray formatting characters
                # Strips *, _, #, and ` while preserving the actual content.
                part = part.replace('*', '').replace('_', '').replace('#', '').replace('`', '')
                
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
