"""Adaptive weighting from settled prediction history."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents import get_all_agents
from ..config import get_settings
from ..database import AgentVote, Prediction


def _agent_provider_map() -> dict[int, str]:
    return {agent.id: agent.provider for agent in get_all_agents()}


def _accuracy_weight(correct: int, total: int) -> float:
    settings = get_settings()
    if total <= 0:
        return 1.0

    # Beta smoothing keeps early streaks from overfitting the next vote.
    smoothing = settings.learning_smoothing
    accuracy = (correct + smoothing * 0.5) / (total + smoothing)
    weight = accuracy / 0.5
    return max(settings.learning_min_weight, min(settings.learning_max_weight, weight))


def _empty_profile() -> dict[str, Any]:
    return {
        "enabled": False,
        "lookback": 0,
        "settled_predictions": 0,
        "agent_weights": {},
        "category_weights": {},
        "provider_weights": {},
        "agent_stats": {},
        "category_stats": {},
        "provider_stats": {},
    }


async def build_learning_profile(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    if not settings.learning_enabled:
        return _empty_profile()

    prediction_rows = (
        (
            await session.execute(
                select(Prediction.id, Prediction.actual_outcome)
                .where(Prediction.actual_outcome.in_(["UP", "DOWN"]))
                .order_by(desc(Prediction.target_at))
                .limit(settings.learning_lookback)
            )
        )
        .all()
    )
    if not prediction_rows:
        return _empty_profile()

    outcome_by_prediction = {row.id: row.actual_outcome for row in prediction_rows}
    prediction_ids = list(outcome_by_prediction)
    provider_by_agent = _agent_provider_map()

    agent_stats: dict[int, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    category_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    provider_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})

    vote_rows = (
        (
            await session.execute(
                select(AgentVote).where(
                    AgentVote.prediction_id.in_(prediction_ids),
                    AgentVote.vote.in_(["UP", "DOWN"]),
                )
            )
        )
        .scalars()
        .all()
    )

    for vote in vote_rows:
        actual = outcome_by_prediction.get(vote.prediction_id)
        if actual not in ("UP", "DOWN"):
            continue
        correct = 1 if vote.vote == actual else 0
        provider = provider_by_agent.get(vote.agent_id, "unknown")

        agent_stats[vote.agent_id]["total"] += 1
        agent_stats[vote.agent_id]["correct"] += correct
        category_stats[vote.agent_category]["total"] += 1
        category_stats[vote.agent_category]["correct"] += correct
        provider_stats[provider]["total"] += 1
        provider_stats[provider]["correct"] += correct

    agent_weights = {}
    for agent_id, stat in agent_stats.items():
        if stat["total"] >= settings.learning_min_agent_samples:
            agent_weights[str(agent_id)] = round(_accuracy_weight(stat["correct"], stat["total"]), 4)

    category_weights = {}
    for category, stat in category_stats.items():
        if stat["total"] >= settings.learning_min_group_samples:
            category_weights[category] = round(_accuracy_weight(stat["correct"], stat["total"]), 4)

    provider_weights = {}
    for provider, stat in provider_stats.items():
        if stat["total"] >= settings.learning_min_group_samples:
            provider_weights[provider] = round(_accuracy_weight(stat["correct"], stat["total"]), 4)

    return {
        "enabled": True,
        "lookback": settings.learning_lookback,
        "settled_predictions": len(prediction_rows),
        "agent_weights": agent_weights,
        "category_weights": category_weights,
        "provider_weights": provider_weights,
        "agent_stats": {
            str(agent_id): {"correct": stat["correct"], "total": stat["total"]}
            for agent_id, stat in agent_stats.items()
        },
        "category_stats": dict(category_stats),
        "provider_stats": dict(provider_stats),
    }
