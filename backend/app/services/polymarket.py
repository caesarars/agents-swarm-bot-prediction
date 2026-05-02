"""Polymarket public Gamma API client.

Pulls active BTC up/down style markets, preferring those that resolve in the next
1 hour to ~3 days (matching the 1-hour swarm horizon).
The Gamma API is public; the API key is included as Bearer for higher rate limits if provided.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    s = get_settings()
    h = {"Accept": "application/json"}
    if s.polymarket_api_key:
        h["Authorization"] = f"Bearer {s.polymarket_api_key}"
    return h


def _as_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _is_btc_market(market: dict[str, Any]) -> bool:
    slug = (market.get("slug") or market.get("ticker") or "").lower()
    question = (market.get("question") or market.get("title") or "").lower()
    if "bitcoin" in slug or "btc" in slug or "bitcoin" in question or "btc" in question:
        return True
    return False


def _is_directional_market(market: dict[str, Any]) -> bool:
    """True if the market is a BTC up/down or price-target market (binary direction)."""
    text = ((market.get("question") or "") + " " + (market.get("slug") or "")).lower()
    if not _is_btc_market(market):
        return False
    keywords = ("up or down", "updown", "above", "below", "reach", "hit", ">", "<", "close above", "close below")
    return any(k in text for k in keywords)


def _normalize_market(market: dict[str, Any], event_slug: str | None = None) -> dict[str, Any]:
    slug = market.get("slug") or event_slug
    return {
        "id": market.get("id") or market.get("conditionId") or slug,
        "slug": slug,
        "question": market.get("question") or market.get("title"),
        "url": f"https://polymarket.com/event/{event_slug or slug}" if (event_slug or slug) else None,
        "volume": market.get("volume") or market.get("volumeNum"),
        "liquidity": market.get("liquidity") or market.get("liquidityNum"),
        "outcomes": market.get("outcomes"),
        "outcome_prices": market.get("outcomePrices"),
        "end_date": market.get("endDate") or market.get("endDateIso"),
    }


def _parse_end_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_in_target_window(end_date: Any) -> bool:
    """Match markets that resolve from now up to ~3 days out (1h horizon-friendly)."""
    parsed = _parse_end_date(end_date)
    if parsed is None:
        return False
    now = datetime.now(timezone.utc)
    return now - timedelta(minutes=5) <= parsed <= now + timedelta(days=3)


def _horizon_score(market: dict[str, Any]) -> float:
    """Lower is better. Prefers markets ending closest to ~1 hour ahead."""
    parsed = _parse_end_date(market.get("end_date"))
    if parsed is None:
        return 1e9
    delta_minutes = (parsed - datetime.now(timezone.utc)).total_seconds() / 60.0
    target = 60.0  # minutes
    if delta_minutes < 0:
        return 1e6 + abs(delta_minutes)
    return abs(delta_minutes - target)


async def _fetch_json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    s = get_settings()
    r = await client.get(f"{s.polymarket_gamma_url}{path}", params=params, headers=_headers())
    r.raise_for_status()
    return r.json()


async def search_btc_short_term_markets(limit: int = 8) -> list[dict[str, Any]]:
    """Surface active BTC up/down style markets, ordered by closeness to a 1h horizon."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            broad = _as_list(
                await _fetch_json(
                    client,
                    "/markets",
                    {
                        "limit": 200,
                        "active": "true",
                        "closed": "false",
                        "order": "endDate",
                        "ascending": "true",
                    },
                )
            )

            candidates: list[dict[str, Any]] = []
            for raw in broad:
                if not _is_btc_market(raw):
                    continue
                if not _is_in_target_window(raw.get("endDate") or raw.get("endDateIso")):
                    continue
                candidates.append(_normalize_market(raw))

            directional = [c for c in candidates if _is_directional_market(c) or _is_directional_market_normalized(c)]
            picks = directional or candidates

            picks.sort(key=_horizon_score)
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for m in picks:
                key = str(m.get("id") or m.get("slug"))
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(m)

            return deduped[:limit]
    except Exception as e:
        log.warning("polymarket fetch failed: %s", e)
        return []


def _is_directional_market_normalized(market: dict[str, Any]) -> bool:
    """Same intent as _is_directional_market but for already-normalized markets."""
    text = ((market.get("question") or "") + " " + (market.get("slug") or "")).lower()
    keywords = ("up or down", "updown", "above", "below", "reach", "hit", ">", "<", "close above", "close below")
    return any(k in text for k in keywords)
