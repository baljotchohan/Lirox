"""Lirox v1.1 — /rag slash command handlers.

Adapter for the ChromaDB-based RAG (RAGStore / RAGIngestor / RAGRetriever).

Wire into main.py's slash dispatcher:

    elif cmd == "/rag" or cmd.startswith("/rag "):
        rest = cmd[5:].strip() if len(cmd) > 5 else ""
        from lirox.rag.commands import handle_rag_command
        handle_rag_command(rest, console)

Actual method contracts (as implemented):

    RAGIngestor()
        .ingest_folder(path: str) -> dict  {"ok", "files", "chunks", "errors", "skipped"}
        .ingest_file(path: str) -> dict    {"ok", "chunks", "file", "error"}
        .reindex_all() -> dict             {"files_indexed", "chunks", "elapsed"}

    RAGStore()
        .add_folder(path: str) -> None
        .remove_folder(path: str) -> None
        .list_folders() -> list[str]
        .stats() -> dict  {"backend", "documents", "persist_dir", "folders"}

    RAGRetriever()
        .retrieve_structured(text: str, n_results: int = 5)
            -> list[{"text", "source", "distance", "chunk_index"}]
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
        backend  = s.get("backend", "?")
        docs     = s.get("documents", "?")
        persist  = s.get("persist_dir", "?")
        console.print(f"[bold]Backend:[/bold]        {backend}")
        console.print(f"[bold]Documents:[/bold]      {docs}")
        console.print(f"[bold]Storage path:[/bold]   {persist}")
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
                result["files_indexed"] += r.get("files", 0)
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
    hits = r.retrieve_structured(arg, n_results=5)
    if not hits:
        console.print("[yellow]No matches.[/yellow]")
        return
    console.print(f"[bold]Top {len(hits)} matches:[/bold]\n")
    seen = set()
    for h in hits:
        source = h.get("source", "?")
        if source in seen:
            continue
        seen.add(source)
        distance = h.get("distance", "?")
        dist_str = f" (distance: {float(distance):.3f})" if isinstance(distance, (int, float)) else ""
        console.print(f"  • {source}{dist_str}")
