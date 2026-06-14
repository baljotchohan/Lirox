"""
[WEB-7] File download endpoints with path validation.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from lirox.config import SAFE_DIRS_RESOLVED, OUTPUTS_DIR

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/download")
async def download_file(path: str = Query(..., description="Absolute file path")):
    """Download a generated file — validated against SAFE_DIRS."""
    canonical = os.path.realpath(os.path.expanduser(path))
    if not any(canonical.startswith(s + os.sep) or canonical == s for s in SAFE_DIRS_RESOLVED):
        raise HTTPException(status_code=403, detail="Path outside permitted directories")
    if not os.path.isfile(canonical):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(canonical, filename=os.path.basename(canonical))


@router.get("/list")
async def list_files() -> Dict[str, Any]:
    """List files in the outputs directory."""
    files = []
    if os.path.isdir(OUTPUTS_DIR):
        for f in sorted(Path(OUTPUTS_DIR).iterdir()):
            if f.is_file():
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": str(f),
                    "modified": f.stat().st_mtime,
                })
    return {"files": files, "directory": OUTPUTS_DIR}
