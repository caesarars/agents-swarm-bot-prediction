import os
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import get_settings


class Base(DeclarativeBase):
    pass


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    target_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    btc_price_at_predict: Mapped[float] = mapped_column(Float)
    btc_price_at_target: Mapped[float | None] = mapped_column(Float, nullable=True)

    up_votes: Mapped[int] = mapped_column(Integer, default=0)
    down_votes: Mapped[int] = mapped_column(Integer, default=0)
    abstain_votes: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    final_prediction: Mapped[str] = mapped_column(String(8))  # UP / DOWN / TIE
    actual_outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_correct: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1/0/null

    category_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    market_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentVote(Base):
    __tablename__ = "agent_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(Integer, index=True)
    agent_id: Mapped[int] = mapped_column(Integer, index=True)
    agent_name: Mapped[str] = mapped_column(String(128))
    agent_category: Mapped[str] = mapped_column(String(64), index=True)
    vote: Mapped[str] = mapped_column(String(8))  # UP / DOWN / ABSTAIN
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


_engine = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _ensure_data_dir(database_url: str) -> None:
    if database_url.startswith("sqlite+aiosqlite:///"):
        path = database_url.replace("sqlite+aiosqlite:///", "")
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)


def get_engine():
    global _engine, _session_maker
    if _engine is None:
        settings = get_settings()
        _ensure_data_dir(settings.database_url)
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
        _session_maker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        get_engine()
    assert _session_maker is not None
    return _session_maker


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
