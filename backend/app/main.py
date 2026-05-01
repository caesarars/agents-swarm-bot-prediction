"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .logging_config import configure_logging
from .routers import predictions
from .services import scheduler

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("DEEPSEEK_API_KEY", settings.deepseek_api_key),
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
            ("GEMINI_API_KEY", settings.gemini_api_key),
        )
        if not value
    ]
    if missing:
        log.warning("missing LLM keys: %s (matching agents will abstain)", ", ".join(missing))
    await init_db()
    sched = scheduler.start_scheduler()
    log.info("app ready (jobs=%s)", [j.id for j in sched.get_jobs()])
    try:
        yield
    finally:
        scheduler.stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BTC 5-Min Swarm Predictor",
        description="Multi-model AI agents predicting BTC up/down for the next 5 minutes.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(predictions.router, prefix="/api")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
