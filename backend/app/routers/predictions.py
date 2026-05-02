from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from ..agents import get_all_agents
from ..config import get_settings
from ..database import AgentVote, Prediction, get_session_maker
from ..services import backtest, learning, market, polymarket, prediction

router = APIRouter()


def _serialize_prediction(p: Prediction) -> dict[str, Any]:
    return {
        "id": p.id,
        "created_at": p.created_at.isoformat() + "Z",
        "target_at": p.target_at.isoformat() + "Z",
        "btc_price_at_predict": p.btc_price_at_predict,
        "btc_price_at_target": p.btc_price_at_target,
        "up_votes": p.up_votes,
        "down_votes": p.down_votes,
        "abstain_votes": p.abstain_votes,
        "avg_confidence": p.avg_confidence,
        "final_prediction": p.final_prediction,
        "actual_outcome": p.actual_outcome,
        "is_correct": p.is_correct,
        "category_breakdown": p.category_breakdown,
        "market_snapshot": p.market_snapshot,
    }


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    settings = get_settings()
    return [
        {
            "id": a.id,
            "name": a.name,
            "category": a.category,
            "provider": a.provider,
            "model": str(getattr(settings, a.model_setting, a.model_setting)),
            "role": a.system_prompt.split("Your analytical lens: ")[-1] if "Your analytical lens: " in a.system_prompt else "",
        }
        for a in get_all_agents()
    ]


@router.get("/predictions/latest")
async def latest_prediction() -> dict[str, Any]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        row = (
            await session.execute(
                select(Prediction).order_by(desc(Prediction.created_at)).limit(1)
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="no predictions yet")
        return _serialize_prediction(row)


@router.get("/predictions/history")
async def prediction_history(limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        rows = (
            (
                await session.execute(
                    select(Prediction).order_by(desc(Prediction.created_at)).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [_serialize_prediction(r) for r in rows]


@router.get("/predictions/{prediction_id}/votes")
async def prediction_votes(prediction_id: int) -> list[dict[str, Any]]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        rows = (
            (
                await session.execute(
                    select(AgentVote)
                    .where(AgentVote.prediction_id == prediction_id)
                    .order_by(AgentVote.agent_id)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "agent_id": v.agent_id,
                "agent_name": v.agent_name,
                "agent_category": v.agent_category,
                "vote": v.vote,
                "confidence": v.confidence,
                "reasoning": v.reasoning,
                "error": v.error,
            }
            for v in rows
        ]


@router.get("/stats")
async def stats() -> dict[str, Any]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        total = (await session.execute(select(func.count(Prediction.id)))).scalar() or 0
        settled = (
            await session.execute(
                select(func.count(Prediction.id)).where(Prediction.actual_outcome.is_not(None))
            )
        ).scalar() or 0
        correct = (
            await session.execute(
                select(func.count(Prediction.id)).where(Prediction.is_correct == 1)
            )
        ).scalar() or 0
        accuracy = (correct / settled) if settled else None
        return {
            "total_predictions": total,
            "settled_predictions": settled,
            "correct_predictions": correct,
            "accuracy": accuracy,
        }


@router.get("/learning/performance")
async def learning_performance() -> dict[str, Any]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        return await learning.build_learning_profile(session)


@router.get("/backtest")
async def backtest_harness(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=20),
    interval: str = Query("1h", min_length=2, max_length=4),
    lookback: int = Query(240, ge=20, le=900),
    horizon_minutes: int = Query(60, ge=1, le=1440),
    threshold_bps: float = Query(0.0, ge=0.0, le=100.0),
    fee_bps: float = Query(0.0, ge=0.0, le=100.0),
) -> dict[str, Any]:
    try:
        return await backtest.run_backtest(
            symbol=symbol,
            interval=interval,
            lookback=lookback,
            horizon_minutes=horizon_minutes,
            threshold_bps=threshold_bps,
            fee_bps=fee_bps,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"backtest failed: {e}") from e


@router.post("/predict/run")
async def run_now() -> dict[str, Any]:
    """Trigger a manual prediction round (useful before scheduler kicks in)."""
    pid = await prediction.run_prediction_round()
    return {"status": "ok", "prediction_id": pid}


@router.post("/predict/settle")
async def settle_now() -> dict[str, Any]:
    settled = await prediction.settle_due_predictions()
    return {"status": "ok", "settled": settled}


@router.get("/market/snapshot")
async def market_snapshot() -> dict[str, Any]:
    return await market.get_market_snapshot("BTCUSDT")


@router.get("/polymarket/btc")
async def polymarket_btc() -> list[dict[str, Any]]:
    return await polymarket.search_btc_short_term_markets()
