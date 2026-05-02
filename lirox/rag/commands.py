"""Lirox v1.1 — /rag slash command handlers.

Adapter for the ChromaDB-based RAG (RAGStore / RAGIngestor / RAGRetriever).

Wire into main.py's slash dispatcher:

    elif cmd == "/rag" or cmd.startswith("/rag "):
        rest = cmd[5:].strip() if len(cmd) > 5 else ""
        from lirox.rag.commands import handle_rag_command
        handle_rag_command(rest, console)

NOTE: This module assumes the following methods exist on your RAG classes.
If your method names differ, adjust the calls below — there are only ~6 of them.

    RAGIngestor()
        .ingest_folder(path: str) -> dict      # walk + chunk + embed + store
        .ingest_file(path: str) -> int         # single file, returns chunks added
        .reindex_all() -> dict                 # walk every registered folder

    RAGStore()
        .add_folder(path: str) -> None
        .remove_folder(path: str) -> None
        .list_folders() -> list[str]
        .stats() -> dict {files, chunks, size_bytes, db_path}

    RAGRetriever()
        .query(text: str, k: int = 5) -> list[{path, text, score}]

If your classes use different names (e.g., `add_path` instead of `add_folder`),
just rename the calls. The 6 grep-ables are: add_folder, remove_folder,
list_folders, stats, ingest_folder, query.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

_logger = logging.getLogger("lirox.rag.commands")

# Lazy singletons — survive across slash commands within one session
_store = None
_ingestor = None
_retriever = None


def _get_store():
    global _store
    if _store is None:
        from lirox.rag.store import RAGStore
        _store = RAGStore()
    return _store


def _get_ingestor():
    global _ingestor
    if _ingestor is None:
        from lirox.rag.ingest import RAGIngestor
        _ingestor = RAGIngestor()
    return _ingestor


def _get_retriever():
    global _retriever
    if _retriever is None:
        from lirox.rag.retriever import RAGRetriever
        _retriever = RAGRetriever()
    return _retriever


def handle_rag_command(rest: str, console) -> None:
    """rest = the part of the line after '/rag '."""
    parts = rest.strip().split(maxsplit=1)
    if not parts:
        _print_help(console)
        return
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    try:
        if sub == "add":
            _add(arg, console)
        elif sub in ("remove", "rm"):
            _remove(arg, console)
        elif sub == "status":
            _status(console)
        elif sub == "reindex":
            _reindex(console)
        elif sub == "query":
            _query(arg, console)
        elif sub == "watch":
            console.print("[yellow]Live watch is deferred to v1.1.1.[/yellow]")
        else:
            _print_help(console)
    except AttributeError as exc:
        # Method name mismatch with your RAG classes — show user
        console.print(
            f"[red]RAG method not found: {exc}[/red]\n"
            f"[dim]Adjust the calls in lirox/rag/commands.py to match "
            f"your store/ingestor/retriever method names.[/dim]"
        )
    except Exception as exc:
        _logger.exception("rag command failed")
        console.print(f"[red]Error: {exc}[/red]")


def _print_help(console) -> None:
    console.print(
        "\n[bold]/rag[/bold] commands:\n"
        "  /rag add <path>     Add a folder to the index\n"
        "  /rag remove <path>  Remove a folder from the index\n"
        "  /rag status         Show indexed folders and stats\n"
        "  /rag reindex        Walk all folders and refresh the index\n"
        "  /rag query <text>   Debug: show top retrieved chunks\n"
    )


def _add(arg: str, console) -> None:
    if not arg:
        console.print("[red]Usage: /rag add <path>[/red]")
        return
    p = Path(arg).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        console.print(f"[red]Not a directory: {p}[/red]")
        return
    _get_store().add_folder(str(p))
    console.print(f"[green]✓ Added folder:[/green] {p}")
    console.print("[dim]Run /rag reindex to build the index now.[/dim]")


def _remove(arg: str, console) -> None:
    if not arg:
        console.print("[red]Usage: /rag remove <path>[/red]")
        return
    p = Path(arg).expanduser().resolve()
    _get_store().remove_folder(str(p))
    console.print(f"[green]✓ Removed folder:[/green] {p}")


def _status(console) -> None:
    store = _get_store()
    folders = store.list_folders()
    s = store.stats() if hasattr(store, "stats") else {}
    console.print()
    console.print(f"[bold]Indexed folders:[/bold] {len(folders)}")
    for f in folders:
        console.print(f"  • {f}")
    if s:
        files = s.get("files", "?")
        chunks = s.get("chunks", "?")
        size = _human_size(s.get("size_bytes", 0)) if "size_bytes" in s else "?"
        db = s.get("db_path", "?")
        console.print(f"[bold]Files indexed:[/bold]  {files}")
        console.print(f"[bold]Chunks:[/bold]         {chunks}")
        console.print(f"[bold]Index size:[/bold]     {size}")
        console.print(f"[bold]Database:[/bold]       {db}")
    console.print()


def _reindex(console) -> None:
    console.print("[dim]Indexing… this may take a few minutes for large folders.[/dim]")
    ing = _get_ingestor()
    if hasattr(ing, "reindex_all"):
        result = ing.reindex_all()
    else:
        # Fall back: manually walk each folder
        folders = _get_store().list_folders()
        result = {"files_indexed": 0, "chunks": 0, "elapsed": 0.0}
        for folder in folders:
            r = ing.ingest_folder(folder)
            if isinstance(r, dict):
                result["files_indexed"] += r.get("files_indexed", 0)
                result["chunks"] += r.get("chunks", 0)
    files = result.get("files_indexed", "?")
    chunks = result.get("chunks", "?")
    elapsed = result.get("elapsed", 0)
    console.print(
        f"[green]✓ Done.[/green] {files} files, {chunks} chunks "
        f"in {elapsed:.1f}s" if isinstance(elapsed, (int, float)) else
        f"[green]✓ Done.[/green] {files} files, {chunks} chunks"
    )


def _query(arg: str, console) -> None:
    if not arg:
        console.print("[red]Usage: /rag query <text>[/red]")
        return
    r = _get_retriever()
    hits = r.query(arg, k=5) if hasattr(r, "query") else []
    if not hits:
        console.print("[yellow]No matches.[/yellow]")
        return
    console.print(f"[bold]Top {len(hits)} matches:[/bold]\n")
    seen = set()
    for h in hits:
        path = h.get("path") or h.get("source") or "?"
        if path in seen:
            continue
        seen.add(path)
        console.print(f"  • {path}")


def _human_size(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
