from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from lirox.server.routes import router
from lirox.config import PROJECT_ROOT
import os

app = FastAPI(title="Lirox Agent OS", version="0.4.1")

# Enable CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes FIRST — these must take priority over static file serving
app.include_router(router)

# Mount static files (Frontend build output) — AFTER API routes
# The /api prefix on all routes prevents conflicts with static serving
static_path = os.path.join(PROJECT_ROOT, "server/static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
else:
    # No static build yet — return a helpful message instead of 404
    @app.get("/")
    def index():
        return JSONResponse({
            "message": "Lirox API server is running.",
            "version": "0.4.1",
            "docs": "http://127.0.0.1:8000/docs",
            "hint": "Frontend not built yet. Run: cd frontend && npm install && npm run build"
        })
