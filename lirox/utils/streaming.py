"""Lirox v1.1 — Streaming Response Engine"""
from __future__ import annotations
import re
import time
from typing import Generator

# Patterns for reasoning preamble sentences that should be stripped
_PREAMBLE_PATTERNS = [
    re.compile(
        r'^(The next step is|I should consider|I need to|Let me think|Given the|I will|'
        r'Additionally,|Furthermore,|As an AI|As a language|I must|I can see|It seems|'
        r'Based on the|First,? I|Note that|So,? I|My approach|To answer|Let me start)'
        r'.*?(?=\n\n|\Z)', re.DOTALL | re.MULTILINE | re.IGNORECASE
    ),
]


class StreamingResponse:
    """Stream responses. Code blocks yielded atomically — never split or truncated."""

    @staticmethod
    def strip_thinking(text: str) -> str:
        """Remove raw LLM reasoning artifacts before the answer is shown.

        Handles:
        - <think>...</think> / <thinking>...</thinking> blocks (DeepSeek/Qwen)
        - Leading reasoning-preamble sentences ("The next step is to…")
        - Blank-line-only leading runs
        """
        if not text:
            return text

        # 1. Strip <think> / <thinking> XML blocks
        text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 2. Strip reasoning preamble paragraphs at the start
        #    We remove contiguous leading paragraphs that look like internal monologue.
        _MONOLOGUE = re.compile(
            r'^(?:The next step|I should consider|I need to|Let me think|Given the '
            r'user|As an AI|As a language model|I will now|Additionally,|'
            r'Furthermore,|I must|It seems like|Based on the|'
            r'So,? I should|My approach|To answer this|Let me start)'
            r'[^\n]*(?:\n(?!\n)[^\n]*)*\n*',
            re.IGNORECASE,
        )
        # Apply up to 5 times to peel multiple preamble paragraphs
        for _ in range(5):
            stripped = _MONOLOGUE.sub('', text.lstrip('\n'), count=1).lstrip('\n')
            if stripped == text.lstrip('\n'):
                break
            text = stripped

        return text.strip()

    @staticmethod
    def clean_formatting(text: str) -> str:
        """Strip thinking artifacts then enforce zero-asterisk formatting policy."""
        if not text:
            return text

        # First strip any raw reasoning content
        text = StreamingResponse.strip_thinking(text)

        # Split by code blocks so we don't touch code
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
