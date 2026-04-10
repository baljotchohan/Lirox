"""
Lirox v1.0.0 — Streaming Response Engine

Yields response text incrementally so the terminal displays a live
"typing" effect rather than dumping the full answer all at once.
"""
from __future__ import annotations

import time
from typing import Generator


class StreamingResponse:
    """Stream responses with a live typing effect."""

    def stream_with_typing(
        self,
        text: str,
        delay: float = 0.01,
        chunk_size: int = 1,
    ) -> Generator[str, None, None]:
        """Yield *text* character-by-character (or in *chunk_size* slices).

        Args:
            text:       The full text to stream.
            delay:      Pause between yields in seconds.
            chunk_size: Number of characters to emit per yield.

        Yields:
            Successive slices of *text*.
        """
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            yield chunk
            if delay > 0:
                time.sleep(delay)

    def stream_in_paragraphs(
        self,
        text: str,
        delay: float = 0.0,
    ) -> Generator[str, None, None]:
        """Yield *text* one paragraph at a time (split on blank lines).

        This produces a natural reading rhythm: each paragraph appears
        fully-formed rather than character-by-character, keeping code
        blocks and lists intact.

        Args:
            text:  The full text to stream.
            delay: Optional pause between paragraphs in seconds.

        Yields:
            Successive paragraphs with their trailing newlines preserved.
        """
        paragraphs = text.split("\n\n")
        last_idx = len(paragraphs) - 1
        for idx, para in enumerate(paragraphs):
            if not para.strip():
                continue
            suffix = "\n\n" if idx < last_idx else ""
            yield para + suffix
            if delay > 0:
                time.sleep(delay)

    def stream_code_block(
        self,
        code: str,
        delay: float = 0.02,
    ) -> Generator[str, None, None]:
        """Yield *code* one line at a time (slower pace for readability).

        Args:
            code:  The code string to stream.
            delay: Pause between lines in seconds.

        Yields:
            Successive lines of *code* with their newlines preserved.
        """
        lines = code.splitlines(keepends=True)
        for line in lines:
            yield line
            if delay > 0:
                time.sleep(delay)
