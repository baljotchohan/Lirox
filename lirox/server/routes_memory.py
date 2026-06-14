"""
[WEB-6] Memory REST endpoints.
"""
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryImportRequest(BaseModel):
    content: str
    source: str = "pasted"


@router.get("/stats")
async def memory_stats() -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    return LearningManager().stats()


@router.get("/facts")
async def list_facts(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    all_facts = LearningManager().recall_facts(limit=limit + offset)
    return {"facts": all_facts[offset:offset + limit], "total": len(all_facts)}


@router.get("/topics")
async def list_topics() -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    return {"topics": LearningManager().recall_topics(limit=20)}


@router.get("/projects")
async def list_projects() -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    return {"projects": LearningManager().recall_projects()}


@router.get("/recall")
async def full_recall() -> Dict[str, Any]:
    from lirox.memory.knowledge_manager import LearningManager
    lm = LearningManager()
    return {
        "facts": lm.recall_facts(limit=30),
        "topics": lm.recall_topics(limit=10),
        "projects": lm.recall_projects(),
        "stats": lm.stats(),
    }


@router.post("/export")
async def export_memory() -> Dict[str, Any]:
    from lirox.memory.exporter import export_learnings
    import json
    path = export_learnings()
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        data = {}
    return {"path": path, "data": data}


@router.post("/import")
async def import_memory(req: MemoryImportRequest) -> Dict[str, Any]:
    from lirox.memory.import_handler import MemoryImporter
    from lirox.memory.learnings import LearningsStore
    result = MemoryImporter(LearningsStore()).import_raw_data(req.content, source=req.source)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Import failed"))
    return result


@router.get("/sync-prompt")
async def get_sync_prompt() -> Dict[str, str]:
    from lirox.memory.sync_prompt import MEMORY_SYNC_PROMPT
    return {"prompt": MEMORY_SYNC_PROMPT}
