"""
[WEB-3] WebSocket endpoint for real-time chat.

Maps MasterOrchestrator.run() events → JSON WebSocket frames.
Uses asyncio.Queue as a bridge between the sync generator and the async WebSocket.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from lirox.server import state

_logger = logging.getLogger("lirox.server.websocket")

# Background thread pool for running the synchronous orchestrator generator
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lirox-ws")

# Strip Rich console markup like [bold #FFC107], [/], [dim], etc.
_RICH_MARKUP_RE = re.compile(r"\[/?[a-zA-Z0-9# _.,:;!@%^&*()+=\-]+?\]")


def strip_rich(text: str) -> str:
    """Remove Rich markup tags from text for clean web display."""
    if not text:
        return ""
    return _RICH_MARKUP_RE.sub("", text)


def _event_to_dict(event) -> Dict[str, Any]:
    """Convert an OrchestratorEvent to a JSON-serializable dict."""
    return {
        "type": event.type,
        "message": strip_rich(event.message or ""),
        "agent": event.agent or "",
        "data": event.data if isinstance(event.data, dict) else {},
        "timestamp": event.timestamp or time.time(),
    }


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket handler at /ws/chat.

    Protocol:
    - On connect: sends {"type": "connected", "data": {version, profile}}
    - Client sends: {"type": "query", "text": "..."} or {"type": "command", "text": "/help"}
    - Server streams OrchestratorEvents as JSON frames
    - Heartbeat: ping every 30s
    """
    await websocket.accept()

    # Send initial connection message
    from lirox.config import APP_VERSION
    try:
        profile_data = state.profile.data if state.profile else {}
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Lirox",
            "agent": "",
            "data": {
                "version": APP_VERSION,
                "profile": profile_data,
                "setup_required": not state.profile.is_setup() if state.profile else True,
            },
            "timestamp": time.time(),
        })
    except Exception as e:
        _logger.error("Failed to send connection message: %s", e)

    # Heartbeat task
    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
        except Exception:
            pass

    heartbeat_task = asyncio.create_task(heartbeat())

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type", "")
            text = raw.get("text", "").strip()

            if msg_type == "pong":
                continue

            if not text:
                await websocket.send_json({
                    "type": "error",
                    "message": "Empty input.",
                    "agent": "",
                    "data": {},
                    "timestamp": time.time(),
                })
                continue

            if msg_type == "query":
                await _handle_query(websocket, text)
            elif msg_type == "command":
                await _handle_command(websocket, text)
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "agent": "",
                    "data": {},
                    "timestamp": time.time(),
                })

    except WebSocketDisconnect:
        _logger.info("WebSocket client disconnected.")
    except Exception as e:
        _logger.error("WebSocket error: %s", e)
    finally:
        heartbeat_task.cancel()


async def _handle_query(websocket: WebSocket, query: str) -> None:
    """Run orchestrator.run(query) in a background thread, forwarding events via WebSocket."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _run_orchestrator():
        try:
            for event in state.orchestrator.run(query):
                loop.call_soon_threadsafe(queue.put_nowait, _event_to_dict(event))
        except Exception as e:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "error",
                    "message": strip_rich(str(e)),
                    "agent": "",
                    "data": {},
                    "timestamp": time.time(),
                },
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    # Submit to thread pool
    _executor.submit(_run_orchestrator)

    # Stream events to client
    while True:
        event = await queue.get()
        if event is None:
            break
        try:
            # Strip Rich markup from nested data messages too
            if "data" in event and isinstance(event["data"], dict):
                for key in ("message", "answer"):
                    if key in event["data"] and isinstance(event["data"][key], str):
                        event["data"][key] = strip_rich(event["data"][key])
            await websocket.send_json(event)
        except Exception as e:
            _logger.warning("Failed to send WebSocket frame: %s", e)
            break


async def _handle_command(websocket: WebSocket, cmd: str) -> None:
    """Execute a slash command and return the result as JSON.

    Instead of using the terminal's handle_command (which writes Rich markup to console),
    we reimplement command handling to return clean JSON data.
    """
    import os
    from pathlib import Path
    from lirox.config import APP_VERSION

    parts = cmd.strip().split()
    base = parts[0].lower()
    result: Dict[str, Any] = {"type": "command_result", "command": cmd, "timestamp": time.time()}

    try:
        if base == "/help":
            result["data"] = {
                "commands": [
                    {"command": "/help", "description": "Show all commands"},
                    {"command": "/code", "description": "Enter persistent coding mode"},
                    {"command": "/setup", "description": "Run setup wizard"},
                    {"command": "/history [n]", "description": "View past conversations"},
                    {"command": "/session", "description": "Current session details"},
                    {"command": "/models", "description": "List available AI providers"},
                    {"command": "/use-model <n>", "description": "Switch default AI provider"},
                    {"command": "/memory", "description": "Show learning statistics"},
                    {"command": "/profile", "description": "View user profile"},
                    {"command": "/reset", "description": "Clear current session"},
                    {"command": "/recall", "description": "Show learned facts about you"},
                    {"command": "/workspace [path]", "description": "Set active directory"},
                    {"command": "/expand thinking", "description": "View last reasoning trace"},
                    {"command": "/export-memory", "description": "Save learnings to JSON"},
                    {"command": "/import-memory", "description": "Import external learnings"},
                    {"command": "/rag add <path>", "description": "Add folder to RAG knowledge base"},
                    {"command": "/rag status", "description": "Show RAG store statistics"},
                    {"command": "/rag reindex", "description": "Rebuild RAG index"},
                    {"command": "/rag query <text>", "description": "Test-query the RAG knowledge base"},
                    {"command": "/restart", "description": "Restart Lirox"},
                    {"command": "/version", "description": "Show version"},
                ]
            }
            result["message"] = "Command list"

        elif base == "/version":
            result["message"] = f"Lirox v{APP_VERSION}"
            result["data"] = {"version": APP_VERSION}

        elif base == "/models":
            from lirox.utils.llm import available_providers
            avail = available_providers()
            providers = []
            for p in avail:
                info = {"name": p, "type": "local" if p in ("ollama", "hf_bnb") else "cloud"}
                if p == "ollama":
                    info["model"] = os.getenv("OLLAMA_MODEL", "llama3")
                elif p == "groq":
                    info["model"] = "llama-3.3-70b-versatile"
                elif p == "gemini":
                    info["model"] = "gemini-2.0-flash"
                providers.append(info)
            result["data"] = {"providers": providers}
            result["message"] = f"{len(avail)} provider(s) available"

        elif base == "/use-model":
            if len(parts) < 2:
                result["type"] = "error"
                result["message"] = "Usage: /use-model <provider_name>"
            else:
                from lirox.utils.llm import available_providers
                p = parts[1].lower()
                avail = available_providers()
                if p not in avail:
                    result["type"] = "error"
                    result["message"] = f"'{p}' not available. Available: {', '.join(avail)}"
                else:
                    state.profile.data["llm_provider"] = p
                    state.profile.save()
                    os.environ["_LIROX_PINNED_MODEL"] = p
                    result["message"] = f"LLM provider pinned to: {p}"
                    result["data"] = {"provider": p}

        elif base == "/memory":
            from lirox.memory.knowledge_manager import LearningManager
            lm = LearningManager()
            stats = lm.stats()
            result["data"] = stats
            result["message"] = "Memory statistics"

        elif base == "/profile":
            result["data"] = state.profile.data if state.profile else {}
            result["message"] = "User profile"

        elif base == "/session":
            s = state.orchestrator.session_store.current()
            result["data"] = {
                "session_id": s.session_id,
                "name": s.name,
                "created_at": s.created_at,
                "entries": len(s.entries),
            }
            result["message"] = "Current session info"

        elif base == "/history":
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
            sessions = state.orchestrator.session_store.list_sessions(limit)
            result["data"] = {
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "name": s.name,
                        "created_at": s.created_at,
                        "entries": len(s.entries),
                        "summary": s.summary(),
                    }
                    for s in sessions
                ]
            }
            result["message"] = f"{len(sessions)} session(s)"

        elif base == "/reset":
            state.orchestrator.session_store.reset() if hasattr(state.orchestrator.session_store, "reset") else state.orchestrator.session_store.new_session()
            result["message"] = "Session reset."

        elif base == "/recall":
            from lirox.memory.knowledge_manager import LearningManager
            lm = LearningManager()
            facts = lm.recall_facts(limit=10)
            result["data"] = {"facts": facts}
            result["message"] = f"{len(facts)} fact(s) recalled" if facts else "No facts learned yet."

        elif base == "/workspace":
            if len(parts) > 1:
                new_path = parts[1]
                os.environ["LIROX_WORKSPACE"] = new_path
                result["message"] = f"Workspace set to: {new_path}"
                result["data"] = {"workspace": new_path}
            else:
                ws = os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop"))
                result["message"] = f"Current workspace: {ws}"
                result["data"] = {"workspace": ws}

        elif base == "/expand":
            if len(parts) > 1 and parts[1] == "thinking":
                from lirox.main import _last_thinking
                if not _last_thinking["steps"] and not _last_thinking.get("full_result"):
                    result["message"] = "No recent thinking trace to expand."
                    result["data"] = {}
                else:
                    result["data"] = {
                        "query": _last_thinking.get("query", ""),
                        "steps": _last_thinking.get("steps", []),
                        "elapsed": _last_thinking.get("elapsed", 0.0),
                        "full_result": _last_thinking.get("full_result"),
                    }
                    result["message"] = "Last thinking trace"
            else:
                result["type"] = "error"
                result["message"] = "Usage: /expand thinking"

        elif base == "/export-memory":
            from lirox.memory.exporter import export_learnings
            path = export_learnings()
            result["message"] = f"Memory exported to: {path}"
            result["data"] = {"path": path}

        elif base == "/rag":
            result.update(_handle_rag_command(cmd))

        elif base == "/restart":
            result["message"] = "Restart not supported in web mode. Refresh the page."

        elif base == "/uninstall":
            result["type"] = "error"
            result["message"] = "Uninstall must be run from the terminal for safety."

        else:
            # For unrecognized commands, try running through as a query
            result["type"] = "error"
            result["message"] = f"Unknown command: {base}. Type /help for available commands."

    except Exception as e:
        result["type"] = "error"
        result["message"] = strip_rich(str(e))

    await websocket.send_json(result)


def _handle_rag_command(cmd: str) -> Dict[str, Any]:
    """Handle /rag sub-commands and return a result dict."""
    rest = cmd[5:].strip() if len(cmd) > 5 else ""
    parts = rest.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if sub == "status":
        try:
            from lirox.rag.store import RAGStore
            store = RAGStore()
            folders = store.list_folders()
            stats = store.stats() if hasattr(store, "stats") else {}
            return {
                "message": f"{len(folders)} folder(s) indexed",
                "data": {"folders": folders, "stats": stats},
            }
        except Exception as e:
            return {"type": "error", "message": f"RAG status error: {e}"}

    elif sub == "add":
        if not arg:
            return {"type": "error", "message": "Usage: /rag add <path>"}
        from pathlib import Path
        p = Path(arg).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            return {"type": "error", "message": f"Not a directory: {p}"}
        try:
            from lirox.rag.store import RAGStore
            RAGStore().add_folder(str(p))
            return {"message": f"Added folder: {p}. Run /rag reindex to build the index."}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    elif sub == "reindex":
        try:
            from lirox.rag.ingest import RAGIngestor
            ing = RAGIngestor()
            if hasattr(ing, "reindex_all"):
                r = ing.reindex_all()
            else:
                from lirox.rag.store import RAGStore
                folders = RAGStore().list_folders()
                r = {"files_indexed": 0, "chunks": 0, "elapsed": 0.0}
                for folder in folders:
                    fr = ing.ingest_folder(folder)
                    if isinstance(fr, dict):
                        r["files_indexed"] += fr.get("files", 0)
                        r["chunks"] += fr.get("chunks", 0)
            return {"message": "Reindex complete", "data": r}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    elif sub == "query":
        if not arg:
            return {"type": "error", "message": "Usage: /rag query <text>"}
        try:
            from lirox.rag.retriever import RAGRetriever
            r = RAGRetriever()
            hits = r.retrieve_structured(arg, n_results=5)
            return {"message": f"{len(hits)} match(es)", "data": {"hits": hits}}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    else:
        return {
            "message": "RAG commands: /rag add <path>, /rag status, /rag reindex, /rag query <text>",
        }
