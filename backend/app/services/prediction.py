"""Orchestrate one full prediction round: snapshot -> swarm -> aggregate -> persist."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents import get_all_agents
from ..config import get_settings
from ..database import AgentVote, Prediction, get_session_maker
from . import deepseek, market

log = logging.getLogger(__name__)


def _aggregate(results: list[deepseek.AgentResult]) -> dict:
    up = down = abstain = 0
    confidences = []
    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"UP": 0, "DOWN": 0, "ABSTAIN": 0})

    for r in results:
        if r.vote == "UP":
            up += 1
        elif r.vote == "DOWN":
            down += 1
        else:
            abstain += 1
        if r.vote in ("UP", "DOWN"):
            confidences.append(r.confidence)
        by_cat[r.agent_category][r.vote] = by_cat[r.agent_category].get(r.vote, 0) + 1

    if up > down:
        final = "UP"
    elif down > up:
        final = "DOWN"
    else:
        final = "TIE"

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return {
        "up_votes": up,
        "down_votes": down,
        "abstain_votes": abstain,
        "avg_confidence": round(avg_conf, 2),
        "final_prediction": final,
        "category_breakdown": dict(by_cat),
    }


async def run_prediction_round() -> int:
    """Runs a single round and returns the new prediction id."""
    settings = get_settings()

    log.info("starting prediction round")
    snapshot = await market.get_market_snapshot("BTCUSDT")
    log.info("snapshot ok price=%s", snapshot["price"])

    agents = get_all_agents()
    results = await deepseek.run_swarm(agents, snapshot)
    agg = _aggregate(results)
    log.info(
        "swarm done up=%d down=%d abstain=%d conf=%.1f -> %s",
        agg["up_votes"],
        agg["down_votes"],
        agg["abstain_votes"],
        agg["avg_confidence"],
        agg["final_prediction"],
    )

    now = datetime.utcnow()
    target = now + timedelta(minutes=settings.prediction_interval_minutes)

    session_maker = get_session_maker()
    async with session_maker() as session:  # type: AsyncSession
        pred = Prediction(
            created_at=now,
            target_at=target,
            btc_price_at_predict=snapshot["price"],
            up_votes=agg["up_votes"],
            down_votes=agg["down_votes"],
            abstain_votes=agg["abstain_votes"],
            avg_confidence=agg["avg_confidence"],
            final_prediction=agg["final_prediction"],
            category_breakdown=agg["category_breakdown"],
            market_snapshot={
                "price": snapshot["price"],
                "pct_change_1m": snapshot["pct_change_1m"],
                "pct_change_24h": snapshot["pct_change_24h"],
                "indicators": snapshot["indicators"],
                "depth_summary": snapshot["depth_summary"],
                "sentiment": snapshot["sentiment"],
            },
        )
        session.add(pred)
        await session.flush()

        for r in results:
            session.add(
                AgentVote(
                    prediction_id=pred.id,
                    agent_id=r.agent_id,
                    agent_name=r.agent_name,
                    agent_category=r.agent_category,
                    vote=r.vote,
                    confidence=r.confidence,
                    reasoning=r.reasoning,
                    error=r.error,
                )
            )

        await session.commit()
        return pred.id


async def settle_due_predictions() -> int:
    """Look up predictions whose target_at has passed and write actual outcome."""
    session_maker = get_session_maker()
    settled = 0
    now = datetime.utcnow()

    async with session_maker() as session:
        stmt = select(Prediction).where(
            Prediction.target_at <= now,
            Prediction.actual_outcome.is_(None),
        )
        rows = (await session.execute(stmt)).scalars().all()

        if not rows:
            return 0

        # Fetch current price once
        try:
            snap = await market.get_market_snapshot("BTCUSDT")
            current_price = snap["price"]
        except Exception as e:
            log.warning("settle: failed to fetch current price: %s", e)
            return 0

        for p in rows:
            if current_price > p.btc_price_at_predict:
                outcome = "UP"
            elif current_price < p.btc_price_at_predict:
                outcome = "DOWN"
            else:
                outcome = "TIE"
            p.actual_outcome = outcome
            p.btc_price_at_target = current_price
            p.is_correct = 1 if (outcome == p.final_prediction and outcome != "TIE") else 0
            settled += 1

        await session.commit()
    log.info("settled %d predictions", settled)
    return settled
