"""Application entrypoint for Refribreak Inventory Core (RIC).
Mounts API routers, initializes SQLite WAL schema, and serves Vanilla frontend.
"""
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.database import init_db
from src.api.routes import api_router
from src.config import APP_HOST, APP_PORT

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    init_db()
    yield


app = FastAPI(
    title="Refribreak Inventory Core (RIC) API",
    version="1.0.0",
    description="Enterprise inventory, production, FEFO lot tracking, and dispatch platform for Refribreak.",
    lifespan=lifespan
)

# Enable CORS for local client development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include JSON REST API router
app.include_router(api_router)

# Mount static folder for CSS, JS, Assets
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    """Serves the Vanilla single page web app."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Refribreak Inventory Core (RIC) API is running. Access /docs for API schema."}


if __name__ == "__main__":
    uvicorn.run("src.main:app", host=APP_HOST, port=APP_PORT, reload=True)
