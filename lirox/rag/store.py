"""Lirox v1.1 — RAG Vector Store

Wraps ChromaDB for local persistent vector storage.
Falls back gracefully to a simple TF-IDF in-memory store if ChromaDB
is not installed, so the system never crashes.

Collections:
  - "lirox_knowledge" — ingested file chunks
  - "lirox_conversations" — summarised past exchanges (future)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lirox.config import DATA_DIR

_logger = logging.getLogger("lirox.rag.store")

RAG_DIR = os.path.join(DATA_DIR, "rag")
_COLLECTION_NAME = "lirox_knowledge"
_MAX_RESULTS = 5


class RAGStore:
    """
    Persistent vector store backed by ChromaDB.

    Thread-safe. Lazy-initialised on first call.
    Degrades to TF-IDF fallback if chromadb is unavailable.
    """

    _instance: Optional["RAGStore"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton — one store per process."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, persist_dir: str = ""):
        if self._initialized:
            return
        self._persist_dir = persist_dir or RAG_DIR
        os.makedirs(self._persist_dir, exist_ok=True)
        self._collection = None
        self._fallback_store: Optional[_TFIDFFallback] = None
        self._using_chromadb = False
        self._folders_path = os.path.join(self._persist_dir, "folders.json")
        self._init_backend()
        self._initialized = True

    def _init_backend(self) -> None:
        """Try ChromaDB first; fall back to TF-IDF."""
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=self._persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._using_chromadb = True
            _logger.info(
                "RAG store initialised with ChromaDB (%d documents)",
                self._collection.count(),
            )
        except ImportError:
            _logger.warning(
                "chromadb not installed — using TF-IDF fallback. "
                "Install for better results: pip install chromadb"
            )
            self._fallback_store = _TFIDFFallback(self._persist_dir)
            self._using_chromadb = False
        except Exception as e:
            _logger.error("ChromaDB init failed (%s) — using TF-IDF fallback", e)
            self._fallback_store = _TFIDFFallback(self._persist_dir)
            self._using_chromadb = False

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def backend_name(self) -> str:
        return "chromadb" if self._using_chromadb else "tfidf-fallback"

    @property
    def document_count(self) -> int:
        if self._using_chromadb and self._collection:
            return self._collection.count()
        if self._fallback_store:
            return self._fallback_store.count()
        return 0

    def add(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add or update a document chunk."""
        meta = metadata or {}
        if self._using_chromadb and self._collection:
            self._collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[meta],
            )
        elif self._fallback_store:
            self._fallback_store.add(doc_id, text, meta)

    def add_batch(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Add multiple chunks in a single call. Returns count added."""
        if not ids:
            return 0
        metas = metadatas or [{}] * len(ids)
        if self._using_chromadb and self._collection:
            # ChromaDB accepts batches natively (up to ~5000 per call)
            batch_size = 500
            added = 0
            for i in range(0, len(ids), batch_size):
                self._collection.upsert(
                    ids=ids[i : i + batch_size],
                    documents=texts[i : i + batch_size],
                    metadatas=metas[i : i + batch_size],
                )
                added += len(ids[i : i + batch_size])
            return added
        elif self._fallback_store:
            for doc_id, text, meta in zip(ids, texts, metas):
                self._fallback_store.add(doc_id, text, meta)
            return len(ids)
        return 0

    def query(
        self, query_text: str, n_results: int = _MAX_RESULTS
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top-N most relevant chunks.

        Returns list of dicts:
            [{"id": ..., "text": ..., "metadata": ..., "distance": ...}, ...]
        """
        if self._using_chromadb and self._collection:
            if self._collection.count() == 0:
                return []
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n_results, self._collection.count()),
            )
            out = []
            for i, doc_id in enumerate(results["ids"][0]):
                out.append({
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                })
            return out
        elif self._fallback_store:
            return self._fallback_store.query(query_text, n_results)
        return []

    def delete(self, doc_id: str) -> None:
        """Remove a document by ID."""
        if self._using_chromadb and self._collection:
            try:
                self._collection.delete(ids=[doc_id])
            except Exception:
                pass
        elif self._fallback_store:
            self._fallback_store.delete(doc_id)

    def clear(self) -> None:
        """Wipe the entire collection."""
        if self._using_chromadb and self._collection:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=self._persist_dir)
                client.delete_collection(_COLLECTION_NAME)
                self._collection = client.get_or_create_collection(
                    name=_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                _logger.error("Failed to clear ChromaDB collection: %s", e)
        elif self._fallback_store:
            self._fallback_store.clear()

    def stats(self) -> Dict[str, Any]:
        """Return store statistics."""
        return {
            "backend": self.backend_name,
            "documents": self.document_count,
            "persist_dir": self._persist_dir,
            "folders": len(self.list_folders()),
        }

    def add_folder(self, path: str) -> None:
        """Register a folder for indexing."""
        folders = set(self.list_folders())
        folders.add(path)
        self._save_folders(list(folders))

    def remove_folder(self, path: str) -> None:
        """Unregister a folder."""
        folders = set(self.list_folders())
        if path in folders:
            folders.remove(path)
            self._save_folders(list(folders))

    def list_folders(self) -> List[str]:
        """Return list of registered folders."""
        try:
            if os.path.exists(self._folders_path):
                with open(self._folders_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_folders(self, folders: List[str]) -> None:
        try:
            with open(self._folders_path, "w", encoding="utf-8") as f:
                json.dump(folders, f, indent=2)
        except Exception as e:
            _logger.error("Failed to save RAG folders: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# TF-IDF FALLBACK — works without any extra dependencies
# ─────────────────────────────────────────────────────────────────────────────

class _TFIDFFallback:
    """
    Minimal TF-IDF similarity store that persists to a JSON file.
    Not as good as ChromaDB embeddings, but works offline with zero deps.
    """

    def __init__(self, persist_dir: str):
        self._path = os.path.join(persist_dir, "tfidf_store.json")
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._docs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._docs = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._docs, f, ensure_ascii=False)
            os.replace(tmp, self._path)
        except Exception as e:
            _logger.error("TF-IDF save failed: %s", e)

    def count(self) -> int:
        return len(self._docs)

    def add(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> None:
        self._docs[doc_id] = {"text": text, "metadata": metadata}
        self._save()

    def delete(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)
        self._save()

    def clear(self) -> None:
        self._docs = {}
        self._save()

    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Simple word-overlap scoring (Jaccard-ish)."""
        if not self._docs:
            return []
        query_words = set(query_text.lower().split())
        scored = []
        for doc_id, doc in self._docs.items():
            doc_words = set(doc["text"].lower().split())
            if not doc_words:
                continue
            overlap = len(query_words & doc_words)
            score = overlap / max(len(query_words | doc_words), 1)
            if overlap >= 1:
                scored.append((score, doc_id, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": doc_id,
                "text": doc["text"],
                "metadata": doc.get("metadata", {}),
                "distance": 1.0 - score,
            }
            for score, doc_id, doc in scored[:n_results]
        ]
