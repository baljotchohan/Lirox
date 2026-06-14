"""
[WEB-5] Setup wizard REST API.

Replaces the terminal's interactive wizard with stateless REST endpoints.
Each wizard step is a separate API call — the frontend drives the state machine.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lirox.server import state

router = APIRouter(prefix="/api/setup", tags=["setup"])

_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")


# ── Request Models ───────────────────────────────────────────────────────────

class ProfileSetupRequest(BaseModel):
    user_name: str = ""
    agent_name: str = "Lirox"
    niche: str = ""
    profession: str = ""
    current_project: str = ""
    goals: List[str] = []
    tone: str = "direct"


class ProviderKeyRequest(BaseModel):
    provider: str
    key: str


class OllamaSetupRequest(BaseModel):
    endpoint: str = "http://localhost:11434"
    model: str = "gemma3"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def setup_status() -> Dict[str, Any]:
    """Is setup complete? Returns current profile data."""
    profile = state.profile
    return {
        "is_setup": profile.is_setup() if profile else False,
        "profile": profile.data if profile else {},
        "niche_options": _NICHE_OPTIONS,
        "agent_name_options": ["Lirox", "Atlas", "Nova", "Rex"],
    }


@router.post("/profile")
async def save_profile(req: ProfileSetupRequest) -> Dict[str, Any]:
    """Save user profile fields (name, agent name, niche, etc.)."""
    profile = state.profile
    if not profile:
        raise HTTPException(status_code=500, detail="Profile not initialized")

    # Update fields
    if req.user_name:
        profile.update("user_name", req.user_name.strip())
    if req.agent_name:
        profile.update("agent_name", req.agent_name.strip())
    if req.niche:
        profile.update("niche", req.niche)
    if req.profession:
        profile.update("profession", req.profession.strip())
    if req.current_project:
        profile.update("current_project", req.current_project.strip())
    if req.tone:
        profile.update("tone", req.tone)
    for g in req.goals:
        if g.strip():
            profile.add_goal(g.strip())

    # Seed learnings
    seeded = _seed_learnings(req)

    # Sync orchestrator
    if state.orchestrator:
        state.orchestrator.profile_data = profile.data

    return {
        "success": True,
        "message": "Profile saved",
        "seeded_facts": seeded,
        "profile": profile.data,
    }


@router.post("/provider")
async def add_provider_key(req: ProviderKeyRequest) -> Dict[str, Any]:
    """Add and verify an API key for a cloud LLM provider."""
    provider = req.provider.strip()
    key = req.key.strip()

    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # Verify the key
    valid, message = _verify_api_key(provider, key)

    if not valid:
        return {"valid": False, "message": message}

    # Save to .env
    env_map = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "aimlapi": "AIMLAPI_KEY",
    }
    env_var = env_map.get(provider.lower())
    if not env_var:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        from dotenv import set_key
        if not Path(_ENV_PATH).exists():
            Path(_ENV_PATH).write_text("# Lirox Configuration\n")
        set_key(_ENV_PATH, env_var, key)
        os.environ[env_var] = key
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save key: {e}")

    # Set as default provider if none set
    if state.profile and not state.profile.data.get("llm_provider"):
        state.profile.update("llm_provider", provider.lower())

    return {"valid": True, "message": f"{provider} key verified and saved."}


@router.delete("/provider")
async def remove_provider_key(req: ProviderKeyRequest) -> Dict[str, Any]:
    """Remove a provider key."""
    env_map = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "aimlapi": "AIMLAPI_KEY",
    }
    env_var = env_map.get(req.provider.lower())
    if not env_var:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    os.environ.pop(env_var, None)

    try:
        from dotenv import set_key
        if Path(_ENV_PATH).exists():
            set_key(_ENV_PATH, env_var, "")
    except Exception:
        pass

    return {"message": f"{req.provider} key removed."}


@router.post("/ollama")
async def setup_ollama(req: OllamaSetupRequest) -> Dict[str, Any]:
    """Configure Ollama local LLM."""
    try:
        from dotenv import set_key
        if not Path(_ENV_PATH).exists():
            Path(_ENV_PATH).write_text("# Lirox Configuration\n")

        set_key(_ENV_PATH, "LOCAL_LLM_ENABLED", "true")
        set_key(_ENV_PATH, "OLLAMA_ENDPOINT", req.endpoint)
        set_key(_ENV_PATH, "OLLAMA_MODEL", req.model)

        os.environ["LOCAL_LLM_ENABLED"] = "true"
        os.environ["OLLAMA_ENDPOINT"] = req.endpoint
        os.environ["OLLAMA_MODEL"] = req.model

        if state.profile:
            state.profile.update("llm_provider", "ollama")

        return {"success": True, "message": f"Ollama configured: {req.model} @ {req.endpoint}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ollama/test")
async def test_ollama() -> Dict[str, Any]:
    """Test Ollama connection and list available models."""
    import requests as req_lib
    endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    try:
        r = req_lib.get(f"{endpoint}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return {"connected": True, "models": models, "endpoint": endpoint}
        return {"connected": False, "message": f"Status {r.status_code}", "endpoint": endpoint}
    except Exception as e:
        return {"connected": False, "message": str(e), "endpoint": endpoint}


# ── Private helpers ──────────────────────────────────────────────────────────

_NICHE_OPTIONS = [
    "Software Development",
    "AI / Machine Learning",
    "Data Science",
    "DevOps / Cloud",
    "Product Management",
    "Design / UX",
    "Marketing / Growth",
    "Finance / Trading",
    "Content Creation",
    "Research / Academia",
    "Founder / Startup",
    "Student",
    "Other",
]


def _verify_api_key(provider: str, key: str) -> tuple:
    """Verify an API key by making a lightweight test request. Returns (valid, message)."""
    import requests as req_lib
    try:
        if provider.lower() == "groq":
            r = req_lib.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5,
            )
        elif provider.lower() == "gemini":
            r = req_lib.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                timeout=5,
            )
        elif provider.lower() == "openrouter":
            r = req_lib.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5,
            )
        elif provider.lower() == "openai":
            r = req_lib.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5,
            )
        elif provider.lower() == "anthropic":
            r = req_lib.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                timeout=5,
            )
            return (r.status_code != 401, "Valid" if r.status_code != 401 else "Invalid API key")
        elif provider.lower() == "deepseek":
            r = req_lib.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5,
            )
        elif provider.lower() == "aimlapi":
            r = req_lib.get(
                "https://api.aimlapi.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5,
            )
        else:
            return (True, "Unknown provider — key saved without verification")

        if r.status_code == 401:
            return (False, "Invalid API key")
        return (True, "Key verified successfully")
    except Exception as e:
        return (True, f"Network error during verification — key saved: {e}")


def _seed_learnings(req: ProfileSetupRequest) -> int:
    """Seed initial learnings from setup data."""
    seeded = 0
    try:
        from lirox.memory.learnings import LearningsStore
        store = LearningsStore()

        if req.user_name and req.user_name.strip().lower() not in ("boss", "operator", ""):
            store.add_fact(f"User's name is {req.user_name}", confidence=1.0, source="setup")
            seeded += 1
        if req.niche:
            store.add_fact(f"Works in {req.niche}", confidence=0.95, source="setup")
            store.bump_topic(req.niche.lower())
            seeded += 1
        if req.profession:
            store.add_fact(f"Role: {req.profession}", confidence=0.95, source="setup")
            seeded += 1
        if req.current_project:
            store.add_project(req.current_project, description="Current main project")
            seeded += 1
        for g in req.goals:
            if g.strip():
                store.add_fact(f"Goal: {g.strip()}", confidence=0.9, source="setup")
                seeded += 1
    except Exception:
        pass
    return seeded
