from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from lirox.server.routes import router
from lirox.config import PROJECT_ROOT
import os

app = FastAPI(title="Lirox Agent OS", version="0.3.1")

# Enable CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount static files (Frontend build output)
static_path = os.path.join(PROJECT_ROOT, "server/static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

@app.get("/")
def index():
    return {"message": "Welcome to Lirox Server. Frontend not yet built or mounted."}
