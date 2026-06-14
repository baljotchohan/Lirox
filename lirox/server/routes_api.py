"""
[WEB-4] REST API endpoints for commands, status, providers, and workspace.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lirox.server import state
from lirox.server.websocket import strip_rich

router = APIRouter(prefix="/api", tags=["api"])


# ── Request Models ───────────────────────────────────────────────────────────

class CommandRequest(BaseModel):
    command: str


class PinProviderRequest(BaseModel):
    provider: str


class WorkspaceRequest(BaseModel):
    path: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Version, provider status, profile summary."""
    from lirox.config import APP_VERSION
    from lirox.utils.llm import available_providers

    avail = available_providers()
    profile_data = state.profile.data if state.profile else {}

    return {
        "version": APP_VERSION,
        "providers": avail,
        "profile": {
            "agent_name": profile_data.get("agent_name", "Lirox"),
            "user_name": profile_data.get("user_name", "Operator"),
            "niche": profile_data.get("niche", ""),
            "current_project": profile_data.get("current_project", ""),
        },
        "setup_complete": state.profile.is_setup() if state.profile else False,
        "workspace": os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop")),
    }


@router.post("/command")
async def execute_command(req: CommandRequest) -> Dict[str, Any]:
    """Execute a slash command and return JSON result."""
    cmd = req.command.strip()
    if not cmd.startswith("/"):
        raise HTTPException(status_code=400, detail="Commands must start with /")

    # Delegate to the WebSocket command handler logic
    from lirox.server.websocket import _handle_command as _ws_cmd
    # Since _handle_command is async and expects a websocket, we reimplement here
    parts = cmd.split()
    base = parts[0].lower()
    result: Dict[str, Any] = {"command": cmd, "success": True}

    try:
        if base == "/help":
            result["data"] = _get_help_list()
        elif base == "/version":
            from lirox.config import APP_VERSION
            result["message"] = f"Lirox v{APP_VERSION}"
        elif base == "/models":
            result["data"] = _get_providers()
        elif base == "/memory":
            result["data"] = _get_memory_stats()
        elif base == "/profile":
            result["data"] = state.profile.data if state.profile else {}
        elif base == "/recall":
            result["data"] = _get_recall()
        elif base == "/session":
            result["data"] = _get_session_info()
        elif base == "/history":
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
            result["data"] = _get_history(limit)
        elif base == "/workspace":
            if len(parts) > 1:
                os.environ["LIROX_WORKSPACE"] = parts[1]
                result["message"] = f"Workspace set to: {parts[1]}"
            else:
                result["data"] = {"workspace": os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop"))}
        elif base == "/expand" and len(parts) > 1 and parts[1] == "thinking":
            result["data"] = _get_thinking_trace()
        else:
            result["message"] = f"Command executed: {cmd}"
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


@router.get("/providers")
async def list_providers() -> Dict[str, Any]:
    """List available LLM providers with health status."""
    return _get_providers()


@router.post("/provider/pin")
async def pin_provider(req: PinProviderRequest) -> Dict[str, Any]:
    """Pin a specific LLM provider."""
    from lirox.utils.llm import available_providers
    p = req.provider.lower()
    avail = available_providers()
    if p not in avail:
        raise HTTPException(
            status_code=400,
            detail=f"'{p}' not available. Available: {', '.join(avail)}",
        )
    state.profile.data["llm_provider"] = p
    state.profile.save()
    os.environ["_LIROX_PINNED_MODEL"] = p
    return {"message": f"Provider pinned to: {p}", "provider": p}


@router.get("/history")
async def get_history(limit: int = 20) -> Dict[str, Any]:
    """Session history."""
    return _get_history(limit)


@router.get("/session")
async def get_session() -> Dict[str, Any]:
    """Current session info."""
    return _get_session_info()


@router.post("/session/reset")
async def reset_session() -> Dict[str, Any]:
    """Reset the current session."""
    if hasattr(state.orchestrator.session_store, "reset"):
        state.orchestrator.session_store.reset()
    else:
        state.orchestrator.session_store.new_session()
    return {"message": "Session reset."}


@router.get("/workspace")
async def get_workspace() -> Dict[str, Any]:
    """Current workspace path."""
    return {"workspace": os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop"))}


@router.post("/workspace")
async def set_workspace(req: WorkspaceRequest) -> Dict[str, Any]:
    """Set workspace path."""
    os.environ["LIROX_WORKSPACE"] = req.path
    return {"message": f"Workspace set to: {req.path}", "workspace": req.path}


@router.get("/thinking/last")
async def get_last_thinking() -> Dict[str, Any]:
    """Last thinking trace data."""
    return _get_thinking_trace()


# ── Helper functions ─────────────────────────────────────────────────────────

def _get_help_list() -> Dict[str, Any]:
    return {
        "commands": [
            {"command": "/help", "description": "Show all commands"},
            {"command": "/code <lang>", "description": "Enter persistent coding mode"},
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
            {"command": "/version", "description": "Show version"},
        ]
    }


def _get_providers() -> Dict[str, Any]:
    from lirox.utils.llm import available_providers
    avail = available_providers()
    providers = []
    for p in avail:
        info: Dict[str, Any] = {
            "name": p,
            "available": True,
            "type": "local" if p in ("ollama", "hf_bnb") else "cloud",
        }
        if p == "ollama":
            info["model"] = os.getenv("OLLAMA_MODEL", "llama3")
        elif p == "groq":
            info["model"] = "llama-3.3-70b-versatile"
        elif p == "gemini":
            info["model"] = "gemini-2.0-flash"
        providers.append(info)
    return {"providers": providers, "pinned": os.getenv("_LIROX_PINNED_MODEL", "")}


def _get_memory_stats() -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    lm = LearningManager()
    return lm.stats()


def _get_recall() -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    lm = LearningManager()
    facts = lm.recall_facts(limit=10)
    return {"facts": facts}


def _get_session_info() -> Dict[str, Any]:
    s = state.orchestrator.session_store.current()
    return {
        "session_id": s.session_id,
        "name": s.name,
        "created_at": s.created_at,
        "entries": len(s.entries),
    }


def _get_history(limit: int = 20) -> Dict[str, Any]:
    sessions = state.orchestrator.session_store.list_sessions(limit)
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "name": s.name,
                "created_at": s.created_at,
                "entries": len(s.entries),
            }
            for s in sessions
        ]
    }


def _get_thinking_trace() -> Dict[str, Any]:
    from lirox.main import _last_thinking
    if not _last_thinking["steps"] and not _last_thinking.get("full_result"):
        return {"message": "No recent thinking trace.", "steps": [], "query": ""}
    return {
        "query": _last_thinking.get("query", ""),
        "steps": _last_thinking.get("steps", []),
        "elapsed": _last_thinking.get("elapsed", 0.0),
        "full_result": _last_thinking.get("full_result"),
    }
