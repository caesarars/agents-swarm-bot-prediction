"""Fetch BTC market snapshot from Binance + sentiment from Alternative.me."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from . import indicators

log = logging.getLogger(__name__)

_BINANCE_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_FNG_URL = "https://api.alternative.me/fng/?limit=1&format=json"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
async def _binance_get(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    headers = {}
    if settings.binance_api_key:
        headers["X-MBX-APIKEY"] = settings.binance_api_key
    r = await client.get(f"{settings.binance_base_url}{path}", params=params, headers=headers)
    r.raise_for_status()
    return r.json()


async def _fetch_klines(client: httpx.AsyncClient, symbol: str, interval: str, limit: int) -> list[dict]:
    raw = await _binance_get(client, "/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    out = []
    for k in raw:
        out.append(
            {
                "open_time": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": int(k[6]),
                "trades": int(k[8]),
            }
        )
    return out


async def _fetch_ticker(client: httpx.AsyncClient, symbol: str) -> dict:
    return await _binance_get(client, "/api/v3/ticker/24hr", {"symbol": symbol})


async def _fetch_book_ticker(client: httpx.AsyncClient, symbol: str) -> dict:
    return await _binance_get(client, "/api/v3/ticker/bookTicker", {"symbol": symbol})


async def _fetch_depth(client: httpx.AsyncClient, symbol: str, limit: int = 20) -> dict:
    return await _binance_get(client, "/api/v3/depth", {"symbol": symbol, "limit": limit})


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
async def _binance_futures_get(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    r = await client.get(f"{settings.binance_futures_base_url}{path}", params=params)
    r.raise_for_status()
    return r.json()


async def _fetch_futures_snapshot(symbol: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_BINANCE_TIMEOUT) as client:
            import asyncio

            premium, open_interest, funding_rates = await asyncio.gather(
                _binance_futures_get(client, "/fapi/v1/premiumIndex", {"symbol": symbol}),
                _binance_futures_get(client, "/fapi/v1/openInterest", {"symbol": symbol}),
                _binance_futures_get(client, "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 8}),
            )
    except Exception as e:
        log.warning("binance futures fetch failed: %s", e)
        return {"available": False, "error": str(e)[:200]}

    recent_funding = []
    for row in funding_rates or []:
        recent_funding.append(
            {
                "funding_time": int(row.get("fundingTime")) if row.get("fundingTime") is not None else None,
                "funding_rate": float(row.get("fundingRate")) if row.get("fundingRate") is not None else None,
            }
        )

    mark_price = float(premium.get("markPrice")) if premium.get("markPrice") is not None else None
    index_price = float(premium.get("indexPrice")) if premium.get("indexPrice") is not None else None
    premium_bps = None
    if mark_price is not None and index_price:
        premium_bps = (mark_price - index_price) / index_price * 10_000

    return {
        "available": True,
        "mark_price": mark_price,
        "index_price": index_price,
        "estimated_settle_price": float(premium.get("estimatedSettlePrice")) if premium.get("estimatedSettlePrice") is not None else None,
        "premium_bps": premium_bps,
        "last_funding_rate": float(premium.get("lastFundingRate")) if premium.get("lastFundingRate") is not None else None,
        "interest_rate": float(premium.get("interestRate")) if premium.get("interestRate") is not None else None,
        "next_funding_time": int(premium.get("nextFundingTime")) if premium.get("nextFundingTime") is not None else None,
        "open_interest": float(open_interest.get("openInterest")) if open_interest.get("openInterest") is not None else None,
        "open_interest_time": int(open_interest.get("time")) if open_interest.get("time") is not None else None,
        "recent_funding_rates": recent_funding,
    }


async def _fetch_fng() -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=_BINANCE_TIMEOUT) as client:
            r = await client.get(_FNG_URL)
            r.raise_for_status()
            data = r.json()
            point = (data or {}).get("data", [{}])[0]
            return {
                "value": int(point.get("value")) if point.get("value") is not None else None,
                "classification": point.get("value_classification"),
            }
    except Exception as e:
        log.warning("fear & greed fetch failed: %s", e)
        return None


def _depth_summary(depth: dict) -> dict:
    bids = depth.get("bids", [])[:10]
    asks = depth.get("asks", [])[:10]
    bid_qty = sum(float(b[1]) for b in bids)
    ask_qty = sum(float(a[1]) for a in asks)
    best_bid = float(bids[0][0]) if bids else None
    best_ask = float(asks[0][0]) if asks else None
    spread = (best_ask - best_bid) if (best_bid and best_ask) else None
    spread_bps = (spread / best_bid * 10_000) if (spread and best_bid) else None
    imbalance = None
    if bid_qty + ask_qty > 0:
        imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty)
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "spread_bps": spread_bps,
        "top10_bid_qty": bid_qty,
        "top10_ask_qty": ask_qty,
        "imbalance": imbalance,
    }


def _compact_candles(candles: list[dict]) -> list[dict]:
    """Trim each candle to fields the LLM needs."""
    out = []
    for c in candles:
        out.append(
            {
                "t": c["close_time"],
                "o": round(c["open"], 2),
                "h": round(c["high"], 2),
                "l": round(c["low"], 2),
                "c": round(c["close"], 2),
                "v": round(c["volume"], 4),
            }
        )
    return out


async def get_market_snapshot(symbol: str = "BTCUSDT") -> dict:
    """Build a single JSON snapshot used as user prompt for every agent.

    Horizon target: 1 hour. Primary timeframe = 1h, intraday context = 15m.
    Indicators are computed on 1h closes so they are aligned with the prediction horizon.
    """
    async with httpx.AsyncClient(timeout=_BINANCE_TIMEOUT) as client:
        import asyncio

        klines_1h, klines_15m, ticker, book, depth = await asyncio.gather(
            _fetch_klines(client, symbol, "1h", 60),
            _fetch_klines(client, symbol, "15m", 24),
            _fetch_ticker(client, symbol),
            _fetch_book_ticker(client, symbol),
            _fetch_depth(client, symbol, 20),
        )

    closes = [k["close"] for k in klines_1h]
    highs = [k["high"] for k in klines_1h]
    lows = [k["low"] for k in klines_1h]
    vols = [k["volume"] for k in klines_1h]

    rsi14 = indicators.rsi(closes, 14)
    ema9 = indicators.ema(closes, 9)
    ema21 = indicators.ema(closes, 21)
    sma20 = indicators.sma(closes, 20)
    macd_v = indicators.macd(closes)
    boll = indicators.bollinger(closes, 20, 2.0)
    atr14 = indicators.atr(highs, lows, closes, 14)
    vwap_v = indicators.vwap(highs, lows, closes, vols)

    last_close = closes[-1]
    prior_close = closes[-2] if len(closes) >= 2 else last_close
    pct_1h = (last_close - prior_close) / prior_close * 100 if prior_close else 0.0

    closes_15m = [k["close"] for k in klines_15m]
    pct_15m = 0.0
    if len(closes_15m) >= 2 and closes_15m[-2]:
        pct_15m = (closes_15m[-1] - closes_15m[-2]) / closes_15m[-2] * 100

    window_high = max(highs[-20:]) if len(highs) >= 1 else None
    window_low = min(lows[-20:]) if len(lows) >= 1 else None

    import asyncio

    fng, futures = await asyncio.gather(_fetch_fng(), _fetch_futures_snapshot(symbol))

    return {
        "symbol": symbol,
        "horizon": "1h",
        "price": last_close,
        "pct_change_1h": round(pct_1h, 4),
        "pct_change_15m": round(pct_15m, 4),
        "pct_change_24h": float(ticker.get("priceChangePercent", 0)) if ticker else None,
        "high_24h": float(ticker["highPrice"]) if ticker else None,
        "low_24h": float(ticker["lowPrice"]) if ticker else None,
        "volume_24h_btc": float(ticker["volume"]) if ticker else None,
        "quote_volume_24h_usdt": float(ticker["quoteVolume"]) if ticker else None,
        "book": {
            "bid": float(book["bidPrice"]) if book else None,
            "ask": float(book["askPrice"]) if book else None,
            "bid_qty": float(book["bidQty"]) if book else None,
            "ask_qty": float(book["askQty"]) if book else None,
        },
        "depth_summary": _depth_summary(depth),
        "indicators": {
            "rsi14": rsi14,
            "ema9": ema9,
            "ema21": ema21,
            "sma20": sma20,
            "macd": macd_v,
            "bollinger": boll,
            "atr14": atr14,
            "vwap": vwap_v,
            "window_high_20": window_high,
            "window_low_20": window_low,
        },
        "candles_1h": _compact_candles(klines_1h[-30:]),
        "candles_15m": _compact_candles(klines_15m[-16:]),
        "sentiment": {"fear_and_greed": fng},
        "futures": futures,
    }
