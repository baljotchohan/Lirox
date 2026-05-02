"""Lirox v1.1 — RAG Retriever

High-level retrieval interface that:
  1. Queries the RAGStore for relevant chunks
  2. Formats them into an LLM-ready context block
  3. Respects token budgets (MAX_CONTEXT_CHARS)
  4. De-duplicates sources

Used by MasterOrchestrator to inject RAG context into every prompt.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from lirox.config import MAX_CONTEXT_CHARS
from lirox.rag.store import RAGStore

_logger = logging.getLogger("lirox.rag.retriever")

_RELEVANCE_THRESHOLD = 0.75  # max distance (cosine) to include


class RAGRetriever:
    """Retrieve and format RAG context for injection into prompts."""

    def __init__(self, store: Optional[RAGStore] = None):
        self.store = store or RAGStore()

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        max_chars: int = 0,
        threshold: float = _RELEVANCE_THRESHOLD,
    ) -> str:
        """
        Retrieve relevant context for a query.

        Args:
            query: The user's question or message.
            n_results: Max number of chunks to fetch.
            max_chars: Max total characters (0 = use config default).
            threshold: Max cosine distance to include (lower = stricter).

        Returns:
            Formatted context string ready for LLM injection.
            Empty string if no relevant documents found.
        """
        if self.store.document_count == 0:
            return ""

        budget = max_chars or MAX_CONTEXT_CHARS
        results = self.store.query(query, n_results=n_results)

        if not results:
            return ""

        # Filter by relevance threshold
        relevant = [r for r in results if r.get("distance", 1.0) <= threshold]
        if not relevant:
            return ""

        # Build context block within budget
        lines = ["── Knowledge Base ──"]
        total_chars = len(lines[0])
        seen_sources = set()

        for i, result in enumerate(relevant):
            text = result["text"].strip()
            meta = result.get("metadata", {})
            source = meta.get("filename", meta.get("source", "unknown"))

            # Source attribution (only show once per source)
            if source not in seen_sources:
                source_line = f"[Source: {source}]"
                seen_sources.add(source)
            else:
                source_line = ""

            chunk_text = text
            # Trim if we're approaching budget
            remaining = budget - total_chars - 50  # leave room for formatting
            if remaining <= 0:
                break
            if len(chunk_text) > remaining:
                chunk_text = chunk_text[:remaining] + "…"

            if source_line:
                lines.append(source_line)
                total_chars += len(source_line) + 1
            lines.append(chunk_text)
            total_chars += len(chunk_text) + 1

            if total_chars >= budget:
                break

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    def retrieve_structured(
        self,
        query: str,
        n_results: int = 5,
        threshold: float = _RELEVANCE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve results as structured data (for programmatic use).

        Returns list of:
            [{"text": ..., "source": ..., "distance": ..., "chunk_index": ...}]
        """
        if self.store.document_count == 0:
            return []

        results = self.store.query(query, n_results=n_results)
        return [
            {
                "text": r["text"],
                "source": r.get("metadata", {}).get("source", "unknown"),
                "distance": r.get("distance", 1.0),
                "chunk_index": r.get("metadata", {}).get("chunk_index", 0),
            }
            for r in results
            if r.get("distance", 1.0) <= threshold
        ]

    @property
    def is_empty(self) -> bool:
        return self.store.document_count == 0

    def stats(self) -> Dict[str, Any]:
        """Return retriever + store statistics."""
        store_stats = self.store.stats()
        store_stats["relevance_threshold"] = _RELEVANCE_THRESHOLD
        return store_stats
