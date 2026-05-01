"""Polymarket public Gamma API client.

Pulls active markets that look like a 5-minute (or short-term) BTC up/down bet.
The Gamma API is public; the API key is included as Bearer for higher rate limits if provided.
"""

from __future__ import annotations

import asyncio
import logging
import time
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


def _is_btc_updown_market(market: dict[str, Any]) -> bool:
    slug = (market.get("slug") or market.get("ticker") or "").lower()
    question = (market.get("question") or market.get("title") or "").lower()
    return slug.startswith("btc-updown-5m") or (
        ("bitcoin" in question or "btc" in question)
        and "up" in question
        and "down" in question
    )


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


def _btc_updown_candidate_slugs(window_count: int = 18) -> list[str]:
    """Polymarket 5m BTC events use btc-updown-5m-{window_start_epoch_seconds}."""
    now = int(time.time())
    current_window = now - (now % 300)
    offsets = range(-1, max(-1, window_count - 1))
    return [f"btc-updown-5m-{current_window + offset * 300}" for offset in offsets]


def _is_recent_or_future(end_date: Any) -> bool:
    if not end_date:
        return False
    try:
        parsed = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed >= datetime.now(timezone.utc) - timedelta(minutes=15)


async def _fetch_json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    s = get_settings()
    r = await client.get(f"{s.polymarket_gamma_url}{path}", params=params, headers=_headers())
    r.raise_for_status()
    return r.json()


async def _fetch_markets_by_slug(client: httpx.AsyncClient, slug: str) -> list[dict[str, Any]]:
    markets = _as_list(await _fetch_json(client, "/markets", {"slug": slug}))
    out = [_normalize_market(m, event_slug=slug) for m in markets if _is_btc_updown_market(m)]
    if out:
        return out

    events = _as_list(await _fetch_json(client, "/events", {"slug": slug}))
    out = []
    for event in events:
        event_slug = event.get("slug") or slug
        for market in event.get("markets") or []:
            if isinstance(market, dict) and _is_btc_updown_market(market):
                out.append(_normalize_market(market, event_slug=event_slug))
    return out


async def search_btc_short_term_markets(limit: int = 8) -> list[dict[str, Any]]:
    """Try to surface active BTC up/down style markets."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            slug_results = await asyncio.gather(
                *[_fetch_markets_by_slug(client, slug) for slug in _btc_updown_candidate_slugs(limit + 8)],
                return_exceptions=True,
            )

            candidate_markets: list[dict[str, Any]] = []
            for result in slug_results:
                if isinstance(result, Exception):
                    log.debug("polymarket slug fetch failed: %s", result)
                    continue
                candidate_markets.extend(result)

            broad = _as_list(
                await _fetch_json(
                    client,
                    "/markets",
                    {
                        "limit": 100,
                        "active": "true",
                        "closed": "false",
                        "order": "endDate",
                        "ascending": "true",
                    },
                )
            )
            broad_markets = [
                _normalize_market(m)
                for m in broad
                if _is_btc_updown_market(m) and _is_recent_or_future(m.get("endDate") or m.get("endDateIso"))
            ]

            deduped: dict[str, dict[str, Any]] = {}
            for market in candidate_markets + broad_markets:
                key = str(market.get("id") or market.get("slug"))
                if key and key not in deduped:
                    deduped[key] = market

            return list(deduped.values())[:limit]
    except Exception as e:
        log.warning("polymarket fetch failed: %s", e)
        return []
