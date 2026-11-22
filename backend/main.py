"""FastAPI entry point for Just Analyze.

Run with:  python -m uvicorn backend.main:app

Not implemented (out of scope for this build): the AI agent, WhatsApp
notifications, EMI tracking, and product returns.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from .api import router
    from .config import load_env
    from .db import init_db
except ImportError:  # run with backend/ on sys.path
    from api import router
    from config import load_env
    from db import init_db


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")

os.makedirs(FRONTEND_DIR, exist_ok=True)

load_env()


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Just Analyze", lifespan=lifespan)

app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    if not os.path.isfile(INDEX_PATH):
        return JSONResponse(
            status_code=404,
            content={"detail": "frontend/index.html not found"},
        )
    return FileResponse(INDEX_PATH)
