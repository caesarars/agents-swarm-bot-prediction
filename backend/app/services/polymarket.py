"""Polymarket public Gamma API client.

Pulls active markets that look like a 5-minute (or short-term) BTC up/down bet.
The Gamma API is public; the API key is included as Bearer for higher rate limits if provided.
"""

from __future__ import annotations

import logging
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


async def search_btc_short_term_markets(limit: int = 8) -> list[dict[str, Any]]:
    """Try to surface active BTC up/down style markets."""
    s = get_settings()
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "order": "volume",
        "ascending": "false",
        "tag": "Bitcoin",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{s.polymarket_gamma_url}/markets", params=params, headers=_headers())
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            out = []
            for m in data or []:
                question = (m.get("question") or m.get("slug") or "").lower()
                if "bitcoin" in question or "btc" in question:
                    out.append(
                        {
                            "id": m.get("id"),
                            "slug": m.get("slug"),
                            "question": m.get("question"),
                            "url": f"https://polymarket.com/event/{m.get('slug')}" if m.get("slug") else None,
                            "volume": m.get("volume"),
                            "liquidity": m.get("liquidity"),
                            "outcomes": m.get("outcomes"),
                            "outcome_prices": m.get("outcomePrices"),
                            "end_date": m.get("endDate"),
                        }
                    )
            return out
    except Exception as e:
        log.warning("polymarket fetch failed: %s", e)
        return []
