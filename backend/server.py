"""
JanVaani — FastAPI application entry point.

Start with:
  uvicorn server:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from lib.db import connect_db, close_db

from routers import system, public, ingestion, sources, processing, review, crawler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    # ── Startup ──
    await connect_db()
    # Seed PIB source entry if not already present
    from lib.db import get_db as _get_db
    from services.crawler_service import ensure_pib_source, ensure_all_sources
    _db = _get_db()
    await ensure_pib_source(_db)
    await ensure_all_sources(_db)
    yield
    # ── Shutdown ──
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="JanVaani API",
        description="Government circular simplification, translation, and audio platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",   # Vite dev server
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Mount all routers under /api ──
    app.include_router(system.router, prefix="/api")
    app.include_router(public.router, prefix="/api")
    app.include_router(ingestion.router, prefix="/api")
    app.include_router(sources.router, prefix="/api")
    app.include_router(processing.router, prefix="/api")
    app.include_router(review.router, prefix="/api")
    app.include_router(crawler.router, prefix="/api")

    return app


app = create_app()
