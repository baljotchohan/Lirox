"""
[WEB-2] FastAPI application with WebSocket + REST + static file serving.
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from lirox.server import state
from lirox.server.websocket import websocket_endpoint
from lirox.server.routes_api import router as api_router
from lirox.server.routes_setup import router as setup_router
from lirox.server.routes_memory import router as memory_router
from lirox.server.routes_files import router as files_router


_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Lirox backend on startup."""
    state.init()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lirox Web UI",
        description="Intelligence as an Operating System — Web Interface",
        lifespan=lifespan,
    )

    # CORS for dev (Vite on :5173 → FastAPI on :3210)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3210", "http://127.0.0.1:5173", "http://127.0.0.1:3210"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # WebSocket
    app.websocket("/ws/chat")(websocket_endpoint)

    # REST routers
    app.include_router(api_router)
    app.include_router(setup_router)
    app.include_router(memory_router)
    app.include_router(files_router)

    # Static files (built React app)
    if _WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_WEB_DIST / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Catch-all: serve index.html for SPA routing."""
            file_path = _WEB_DIST / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(_WEB_DIST / "index.html"))

    return app
