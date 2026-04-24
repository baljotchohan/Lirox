"""Lirox v1.1 — Memory Importer

Import learning data for the /import-memory command.
Supports:
  - Lirox native exports
  - ChatGPT / OpenAI exports
  - Claude exports
  - Gemini exports
  - Paste-from-clipboard (interactive)
  - File path (non-interactive)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def import_learnings(file_path: str) -> Dict[str, int]:
    """
    Import learnings from a file path (non-interactive).

    Args:
        file_path: Path to the JSON export file.

    Returns:
        Dict with counts of imported items: {facts, prefs, topics, projects}.
    """
    p = Path(file_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Import file not found: {file_path}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _import_data(data)


def import_memory_interactive() -> bool:
    """
    Interactive import — asks user to choose:
    1. Paste JSON directly
    2. Load from file path
    3. Cancel

    Returns:
        True if import was successful, False otherwise.
    """
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()

    console.print("\n[bold cyan]Import Memory Data[/bold cyan]\n")
    console.print("Choose import method:")
    console.print("  1. Paste JSON text directly")
    console.print("  2. Load from file path")
    console.print("  3. Cancel\n")

    choice = Prompt.ask("Select option", choices=["1", "2", "3"], default="1")

    if choice == "3":
        console.print("[dim]Import cancelled[/dim]")
        return False

    if choice == "1":
        # ── PASTE MODE ──
        console.print(
            "\n[yellow]Paste your JSON data below, then press Enter twice to submit:[/yellow]\n"
        )

        lines = []
        empty_count = 0

        while True:
            try:
                line = input()
                if not line.strip():
                    empty_count += 1
                    if empty_count >= 2:
                        break
                    lines.append(line)
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break

        if not lines:
            console.print("[red]No data pasted[/red]")
            return False

        json_text = "\n".join(lines)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON: {e}[/red]")
            return False

        result = _import_data(data)
        _print_result(console, result)
        return True

    else:
        # ── FILE MODE ──
        file_path = Prompt.ask("Enter file path")

        p = Path(file_path).expanduser()
        if not p.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            return False

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            return False

        result = _import_data(data)
        _print_result(console, result)
        return True


def _print_result(console, result: Dict[str, int]) -> None:
    """Print import results."""
    total = sum(result.values())
    console.print(f"\n[green]✓ Imported {total} items[/green]")
    for key, count in result.items():
        if count > 0:
            console.print(f"  {key}: {count}")


def _import_data(data: Dict[str, Any]) -> Dict[str, int]:
    """
    Import memory data from parsed JSON.

    Supports formats:
    - Lirox native export (has source == 'Lirox')
    - ChatGPT / OpenAI export
    - Claude export
    - Gemini export
    - Unknown format (best-effort)

    Returns:
        Dict with counts: {facts, prefs, topics, projects}.
    """
    from lirox.mind.learnings import LearningsStore

    learnings = LearningsStore()
    stats = {"facts": 0, "prefs": 0, "topics": 0, "projects": 0}

    source = data.get("source", "unknown")

    if source == "Lirox":
        stats = _import_lirox_native(data, learnings)
    elif source in ("ChatGPT", "OpenAI"):
        stats = _import_chatgpt(data, learnings)
    elif source == "Claude":
        stats = _import_claude(data, learnings)
    elif source == "Gemini":
        stats = _import_gemini(data, learnings)
    else:
        stats = _import_best_effort(data, learnings)

    return stats


def _import_lirox_native(
    data: Dict[str, Any], learnings
) -> Dict[str, int]:
    """Import from Lirox's own export format."""
    stats = {"facts": 0, "prefs": 0, "topics": 0, "projects": 0}

    # Facts
    for fact_entry in data.get("facts", []):
        text = fact_entry.get("fact", "") if isinstance(fact_entry, dict) else str(fact_entry)
        if text:
            try:
                learnings.add_fact(text)
                stats["facts"] += 1
            except Exception:
                pass

    # Topics
    topics = data.get("topics", {})
    if isinstance(topics, dict):
        for topic_name in topics:
            try:
                learnings.bump_topic(topic_name)
                stats["topics"] += 1
            except Exception:
                pass

    # Preferences
    prefs = data.get("preferences", {})
    if isinstance(prefs, dict):
        for cat, pref_list in prefs.items():
            if isinstance(pref_list, list):
                for pref in pref_list:
                    try:
                        learnings.add_preference(cat, str(pref))
                        stats["prefs"] += 1
                    except Exception:
                        pass

    # Projects
    for proj in data.get("projects", []):
        if isinstance(proj, dict) and proj.get("name"):
            try:
                learnings.add_project(proj["name"], proj.get("description", ""))
                stats["projects"] += 1
            except Exception:
                pass

    # Update profile if present
    profile_data = data.get("profile", {})
    if profile_data:
        try:
            from lirox.agent.profile import UserProfile
            profile = UserProfile()
            if "user_name" in profile_data:
                profile.data["user_name"] = profile_data["user_name"]
            if "niche" in profile_data:
                profile.data["niche"] = profile_data["niche"]
            profile.save()
        except Exception:
            pass

    return stats


def _import_chatgpt(
    data: Dict[str, Any], learnings
) -> Dict[str, int]:
    """Import from ChatGPT/OpenAI export format."""
    stats = {"facts": 0, "prefs": 0, "topics": 0, "projects": 0}

    conversations = data.get("conversations", data.get("data", []))
    for conv in conversations[:20]:
        title = conv.get("title", "")
        if title:
            try:
                learnings.add_fact(f"Previous topic: {title}")
                stats["facts"] += 1
            except Exception:
                pass

    return stats


def _import_claude(
    data: Dict[str, Any], learnings
) -> Dict[str, int]:
    """Import from Claude export format."""
    stats = {"facts": 0, "prefs": 0, "topics": 0, "projects": 0}

    chats = data.get("chats", data.get("conversations", []))
    for chat in chats[:20]:
        name = chat.get("name", chat.get("title", ""))
        if name:
            try:
                learnings.add_fact(f"Previous topic: {name}")
                stats["facts"] += 1
            except Exception:
                pass

    return stats


def _import_gemini(
    data: Dict[str, Any], learnings
) -> Dict[str, int]:
    """Import from Gemini export format."""
    stats = {"facts": 0, "prefs": 0, "topics": 0, "projects": 0}

    history = data.get("history", data.get("conversations", []))
    for item in history[:20]:
        query = item.get("query", item.get("title", ""))
        if query:
            try:
                learnings.add_fact(f"Previous query: {query}")
                stats["facts"] += 1
            except Exception:
                pass

    return stats


def _import_best_effort(
    data: Dict[str, Any], learnings
) -> Dict[str, int]:
    """Best-effort import for unknown formats."""
    stats = {"facts": 0, "prefs": 0, "topics": 0, "projects": 0}

    # Look for any common keys containing lists of importable data
    for key in ("facts", "memories", "history", "data", "content", "items"):
        items = data.get(key)
        if isinstance(items, list):
            for item in items[:30]:
                text = None
                if isinstance(item, str):
                    text = item
                elif isinstance(item, dict):
                    text = (
                        item.get("text")
                        or item.get("fact")
                        or item.get("content")
                        or item.get("title")
                    )
                if text and isinstance(text, str) and len(text.strip()) > 3:
                    try:
                        learnings.add_fact(text.strip())
                        stats["facts"] += 1
                    except Exception:
                        pass

    return stats
