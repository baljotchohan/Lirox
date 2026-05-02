"""Lirox v1.1 — RAG Document Ingestor

Reads local files, splits them into overlapping chunks, and pushes them
into the RAGStore.  Supports:
  - Plain text (.txt, .md, .log, .csv)
  - Code files (.py, .js, .ts, .go, .rs, .java, .c, .cpp, .rb, .sh)
  - JSON / YAML / TOML
  - PDF (via reportlab text extraction, best-effort)

Chunking strategy:
  - Fixed-size with overlap (default 800 chars / 200 overlap)
  - Each chunk carries metadata: {source, chunk_index, total_chunks}
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lirox.rag.store import RAGStore
from lirox.rag.extractors import extract_rich, is_rich_format

_logger = logging.getLogger("lirox.rag.ingest")

# Extensions we know how to read
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".log", ".csv", ".tsv",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".sh", ".bash",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".html", ".css", ".scss", ".sql", ".xml", ".json",
    ".r", ".swift", ".kt", ".scala", ".lua", ".pl",
}

_DEFAULT_CHUNK_SIZE = 800  # characters
_DEFAULT_OVERLAP = 200


class RAGIngestor:
    """Ingest files into the RAG store."""

    def __init__(self, store: Optional[RAGStore] = None):
        self.store = store or RAGStore()

    def ingest_file(
        self,
        file_path: str,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> Dict[str, Any]:
        """
        Ingest a single file.

        Returns:
            {"ok": bool, "chunks": int, "file": str, "error": str}
        """
        p = Path(file_path).expanduser().resolve()

        if not p.exists():
            return {"ok": False, "chunks": 0, "file": str(p), "error": "File not found"}
        if not p.is_file():
            return {"ok": False, "chunks": 0, "file": str(p), "error": "Not a file"}

        ext = p.suffix.lower()

        # Read content
        try:
            if is_rich_format(p):
                content = extract_rich(p)
            elif ext == ".json":
                content = self._read_json(p)
            elif ext in _TEXT_EXTENSIONS or ext == "":
                content = p.read_text(encoding="utf-8", errors="replace")
            else:
                # Try reading as text anyway
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    return {"ok": False, "chunks": 0, "file": str(p),
                            "error": f"Unsupported file type: {ext}"}
        except Exception as e:
            return {"ok": False, "chunks": 0, "file": str(p), "error": str(e)}

        if not content or not content.strip():
            return {"ok": False, "chunks": 0, "file": str(p), "error": "File is empty"}

        # Chunk
        chunks = self._chunk_text(content, chunk_size, overlap)
        if not chunks:
            return {"ok": False, "chunks": 0, "file": str(p), "error": "No chunks produced"}

        # Generate stable IDs
        file_hash = hashlib.md5(str(p).encode()).hexdigest()[:12]
        ids = [f"{file_hash}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": str(p),
                "filename": p.name,
                "extension": ext,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i in range(len(chunks))
        ]

        added = self.store.add_batch(ids, chunks, metadatas)
        _logger.info("Ingested %s → %d chunks", p.name, added)

        return {"ok": True, "chunks": added, "file": str(p), "error": ""}

    def ingest_directory(
        self,
        dir_path: str,
        recursive: bool = True,
        extensions: Optional[set] = None,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> Dict[str, Any]:
        """
        Ingest all supported files in a directory.

        Returns:
            {"ok": bool, "files": int, "chunks": int, "errors": list, "skipped": int}
        """
        d = Path(dir_path).expanduser().resolve()
        if not d.is_dir():
            return {"ok": False, "files": 0, "chunks": 0, "errors": ["Not a directory"], "skipped": 0}

        allowed_ext = extensions or _TEXT_EXTENSIONS
        glob_fn = d.rglob if recursive else d.glob
        results = {"ok": True, "files": 0, "chunks": 0, "errors": [], "skipped": 0}

        for file_path in sorted(glob_fn("*")):
            if not file_path.is_file():
                continue
            # Skip hidden files and common noise
            if any(part.startswith(".") for part in file_path.parts):
                results["skipped"] += 1
                continue
            if file_path.name in {"package-lock.json", "yarn.lock", "Cargo.lock"}:
                results["skipped"] += 1
                continue
            if file_path.suffix.lower() not in allowed_ext:
                results["skipped"] += 1
                continue
            # Skip large files (>1MB)
            try:
                if file_path.stat().st_size > 1_000_000:
                    results["skipped"] += 1
                    continue
            except OSError:
                continue

            r = self.ingest_file(str(file_path), chunk_size, overlap)
            if r["ok"]:
                results["files"] += 1
                results["chunks"] += r["chunks"]
            else:
                results["errors"].append(f"{file_path.name}: {r['error']}")

        if results["errors"]:
            results["ok"] = results["files"] > 0  # partial success

        return results

    def ingest_folder(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for ingest_directory."""
        return self.ingest_directory(*args, **kwargs)

    def reindex_all(self) -> Dict[str, Any]:
        """Walk every registered folder and refresh the index."""
        import time
        start = time.time()
        folders = self.store.list_folders()
        results = {"files_indexed": 0, "chunks": 0, "elapsed": 0.0}
        
        for folder in folders:
            r = self.ingest_folder(folder)
            results["files_indexed"] += r.get("files", 0)
            results["chunks"] += r.get("chunks", 0)
            
        results["elapsed"] = time.time() - start
        return results

    def ingest_text(
        self,
        text: str,
        source_name: str = "pasted_text",
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> Dict[str, Any]:
        """
        Ingest raw text (e.g. from clipboard paste).

        Returns:
            {"ok": bool, "chunks": int, "source": str}
        """
        if not text or not text.strip():
            return {"ok": False, "chunks": 0, "source": source_name}

        chunks = self._chunk_text(text, chunk_size, overlap)
        text_hash = hashlib.md5(text[:500].encode()).hexdigest()[:12]
        ids = [f"{text_hash}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": source_name, "chunk_index": i, "total_chunks": len(chunks)}
            for i in range(len(chunks))
        ]

        added = self.store.add_batch(ids, chunks, metadatas)
        return {"ok": True, "chunks": added, "source": source_name}

    # ── Chunking ─────────────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks, respecting paragraph boundaries."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        # Try to split on paragraph boundaries first
        paragraphs = re.split(r"\n{2,}", text)
        chunks: List[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 <= chunk_size:
                current = f"{current}\n\n{para}" if current else para
            else:
                if current:
                    chunks.append(current)
                # If a single paragraph exceeds chunk_size, force-split it
                if len(para) > chunk_size:
                    for i in range(0, len(para), chunk_size - overlap):
                        sub = para[i : i + chunk_size]
                        if sub.strip():
                            chunks.append(sub.strip())
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        return chunks

    # ── File readers ─────────────────────────────────────────────────────

    @staticmethod
    def _read_json(path: Path) -> str:
        """Read JSON and flatten to readable text."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, indent=2, ensure_ascii=False, default=str)[:50000]
        except Exception as e:
            return f"[JSON parse error: {e}]"
