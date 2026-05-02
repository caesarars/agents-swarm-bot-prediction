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
from . import deepseek, learning, market

log = logging.getLogger(__name__)


def _aggregate(results: list[deepseek.AgentResult], learning_profile: dict | None = None) -> dict:
    settings = get_settings()
    learning_profile = learning_profile or {}
    up = down = abstain = 0
    confidences = []
    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"UP": 0, "DOWN": 0, "ABSTAIN": 0})
    by_provider: dict[str, dict[str, float | int | str]] = defaultdict(
        lambda: {"UP": 0, "DOWN": 0, "ABSTAIN": 0, "score": 0.0, "direction": "TIE"}
    )
    provider_weights = {
        "deepseek": settings.swarm_deepseek_weight,
        "anthropic": settings.swarm_anthropic_weight,
        "gemini": settings.swarm_gemini_weight,
    }
    learned_agent_weights = learning_profile.get("agent_weights") or {}
    learned_category_weights = learning_profile.get("category_weights") or {}
    learned_provider_weights = learning_profile.get("provider_weights") or {}
    effective_vote_weights: dict[str, float] = {}

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
        by_provider[r.provider][r.vote] = int(by_provider[r.provider].get(r.vote, 0)) + 1

        if r.vote in ("UP", "DOWN"):
            sign = 1 if r.vote == "UP" else -1
            confidence_edge = max(0.05, (r.confidence - 50.0) / 50.0)
            learned_weight = (
                float(learned_agent_weights.get(str(r.agent_id), 1.0))
                * float(learned_category_weights.get(r.agent_category, 1.0))
                * float(learned_provider_weights.get(r.provider, 1.0))
            )
            weight = provider_weights.get(r.provider, 0.5) * learned_weight
            effective_vote_weights[str(r.agent_id)] = round(weight, 4)
            by_provider[r.provider]["score"] = float(by_provider[r.provider]["score"]) + sign * confidence_edge * weight

    for provider, row in by_provider.items():
        score = float(row["score"])
        if score > 0:
            row["direction"] = "UP"
        elif score < 0:
            row["direction"] = "DOWN"

    raw_final = "UP" if up > down else "DOWN" if down > up else "TIE"
    final = raw_final
    total_score = sum(float(row["score"]) for row in by_provider.values())
    weighted_final = "UP" if total_score > 0 else "DOWN" if total_score < 0 else "TIE"

    if settings.swarm_aggregation_mode == "primary_confirm":
        primary_provider = settings.swarm_primary_provider
        primary_score = float(by_provider.get(primary_provider, {}).get("score", 0.0))
        primary_final = "UP" if primary_score > 0 else "DOWN" if primary_score < 0 else "TIE"

        if primary_final == "TIE":
            final = weighted_final
        elif abs(primary_score) >= settings.swarm_primary_min_margin:
            final = primary_final
        elif weighted_final != "TIE" and weighted_final != primary_final and abs(total_score) >= settings.swarm_override_margin:
            final = weighted_final
        else:
            final = primary_final
    elif settings.swarm_aggregation_mode == "weighted":
        final = weighted_final

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return {
        "up_votes": up,
        "down_votes": down,
        "abstain_votes": abstain,
        "avg_confidence": round(avg_conf, 2),
        "final_prediction": final,
        "category_breakdown": dict(by_cat),
        "provider_breakdown": dict(by_provider),
        "learning": {
            "enabled": bool(learning_profile.get("enabled")),
            "settled_predictions": learning_profile.get("settled_predictions", 0),
            "agent_weights": learned_agent_weights,
            "category_weights": learned_category_weights,
            "provider_weights": learned_provider_weights,
            "effective_vote_weights": effective_vote_weights,
        },
        "raw_vote_prediction": raw_final,
        "weighted_prediction": weighted_final,
        "weighted_score": round(total_score, 4),
    }


async def run_prediction_round() -> int:
    """Runs a single round and returns the new prediction id."""
    settings = get_settings()

    log.info("starting prediction round")
    snapshot = await market.get_market_snapshot("BTCUSDT")
    log.info("snapshot ok price=%s", snapshot["price"])

    agents = get_all_agents()
    results = await deepseek.run_swarm(agents, snapshot)

    now = datetime.utcnow()
    target = now + timedelta(minutes=settings.prediction_interval_minutes)

    session_maker = get_session_maker()
    async with session_maker() as session:  # type: AsyncSession
        learning_profile = await learning.build_learning_profile(session)
        agg = _aggregate(results, learning_profile)
        log.info(
            "swarm done up=%d down=%d abstain=%d conf=%.1f score=%.3f learned_rounds=%d -> %s",
            agg["up_votes"],
            agg["down_votes"],
            agg["abstain_votes"],
            agg["avg_confidence"],
            agg["weighted_score"],
            agg["learning"]["settled_predictions"],
            agg["final_prediction"],
        )

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
                "futures": snapshot.get("futures"),
                "aggregation": {
                    "mode": settings.swarm_aggregation_mode,
                    "primary_provider": settings.swarm_primary_provider,
                    "raw_vote_prediction": agg["raw_vote_prediction"],
                    "weighted_prediction": agg["weighted_prediction"],
                    "weighted_score": agg["weighted_score"],
                    "provider_breakdown": agg["provider_breakdown"],
                    "learning": agg["learning"],
                },
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
