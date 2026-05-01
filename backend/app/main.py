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
    if not settings.deepseek_api_key:
        log.warning("DEEPSEEK_API_KEY missing — /predict/run will fail until you set it")
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
        description="100 DeepSeek-powered AI agents predicting BTC up/down for the next 5 minutes.",
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
