"""Historical backtesting harness for the BTC 1-hour direction workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import get_settings
from . import indicators

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=4.0)
_MAX_BINANCE_LIMIT = 1000
_WARMUP_CANDLES = 60


@dataclass(frozen=True)
class Signal:
    vote: str
    confidence: float
    reason: str


def _ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


async def _fetch_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    settings = get_settings()
    headers = {}
    if settings.binance_api_key:
        headers["X-MBX-APIKEY"] = settings.binance_api_key

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{settings.binance_base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            headers=headers,
        )
        response.raise_for_status()
        raw = response.json()

    candles = []
    for k in raw:
        candles.append(
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
    return candles


def _vote_from_signals(signals: list[Signal]) -> dict[str, Any]:
    up = sum(1 for s in signals if s.vote == "UP")
    down = sum(1 for s in signals if s.vote == "DOWN")
    abstain = sum(1 for s in signals if s.vote == "ABSTAIN")

    directional = [s.confidence for s in signals if s.vote in ("UP", "DOWN")]
    avg_confidence = sum(directional) / len(directional) if directional else 0.0

    if up > down:
        final = "UP"
    elif down > up:
        final = "DOWN"
    else:
        final = "TIE"

    return {
        "up_votes": up,
        "down_votes": down,
        "abstain_votes": abstain,
        "avg_confidence": round(avg_confidence, 2),
        "final_prediction": final,
        "signals": [{"vote": s.vote, "confidence": round(s.confidence, 2), "reason": s.reason} for s in signals],
    }


def _confidence(value: float, scale: float, base: float = 52.0, cap: float = 88.0) -> float:
    if scale <= 0:
        return base
    return max(base, min(cap, base + abs(value) / scale * 18.0))


def _technical_signals(candles: list[dict[str, Any]]) -> list[Signal]:
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["volume"] for c in candles]

    close = closes[-1]
    open_ = candles[-1]["open"]
    atr14 = indicators.atr(highs, lows, closes, 14) or max(close * 0.001, 1.0)
    rsi14 = indicators.rsi(closes, 14)
    ema9 = indicators.ema(closes, 9)
    ema21 = indicators.ema(closes, 21)
    sma20 = indicators.sma(closes, 20)
    macd = indicators.macd(closes)
    boll = indicators.bollinger(closes, 20, 2.0)
    vwap = indicators.vwap(highs[-20:], lows[-20:], closes[-20:], volumes[-20:])

    signals: list[Signal] = []

    if ema9 is not None and ema21 is not None:
        spread = ema9 - ema21
        if spread > 0:
            signals.append(Signal("UP", _confidence(spread, atr14), "ema9 above ema21"))
        elif spread < 0:
            signals.append(Signal("DOWN", _confidence(spread, atr14), "ema9 below ema21"))
        else:
            signals.append(Signal("ABSTAIN", 0.0, "ema flat"))

    hist = macd.get("histogram")
    if hist is not None:
        if hist > 0:
            signals.append(Signal("UP", _confidence(hist, atr14 * 0.25), "positive macd histogram"))
        elif hist < 0:
            signals.append(Signal("DOWN", _confidence(hist, atr14 * 0.25), "negative macd histogram"))
        else:
            signals.append(Signal("ABSTAIN", 0.0, "macd neutral"))

    if rsi14 is not None:
        if rsi14 < 35:
            signals.append(Signal("UP", _confidence(35 - rsi14, 15), "rsi oversold"))
        elif rsi14 > 65:
            signals.append(Signal("DOWN", _confidence(rsi14 - 65, 15), "rsi overbought"))
        elif rsi14 > 52:
            signals.append(Signal("UP", _confidence(rsi14 - 52, 20), "rsi positive regime"))
        elif rsi14 < 48:
            signals.append(Signal("DOWN", _confidence(48 - rsi14, 20), "rsi negative regime"))
        else:
            signals.append(Signal("ABSTAIN", 0.0, "rsi neutral"))

    upper = boll.get("upper")
    lower = boll.get("lower")
    middle = boll.get("middle")
    if upper is not None and lower is not None and middle is not None:
        if close > upper:
            signals.append(Signal("DOWN", _confidence(close - upper, atr14), "close above bollinger upper"))
        elif close < lower:
            signals.append(Signal("UP", _confidence(lower - close, atr14), "close below bollinger lower"))
        elif close > middle:
            signals.append(Signal("UP", _confidence(close - middle, atr14 * 1.5), "close above bollinger middle"))
        elif close < middle:
            signals.append(Signal("DOWN", _confidence(middle - close, atr14 * 1.5), "close below bollinger middle"))

    if vwap is not None:
        if close > vwap:
            signals.append(Signal("UP", _confidence(close - vwap, atr14), "close above local vwap"))
        elif close < vwap:
            signals.append(Signal("DOWN", _confidence(vwap - close, atr14), "close below local vwap"))

    if len(closes) >= 6:
        ret_5 = (close - closes[-6]) / closes[-6] * 10_000
        if ret_5 > 5:
            signals.append(Signal("UP", _confidence(ret_5, 25), "positive recent momentum"))
        elif ret_5 < -5:
            signals.append(Signal("DOWN", _confidence(ret_5, 25), "negative recent momentum"))
        else:
            signals.append(Signal("ABSTAIN", 0.0, "recent momentum muted"))

    if len(candles) >= 21:
        prior_high = max(c["high"] for c in candles[-21:-1])
        prior_low = min(c["low"] for c in candles[-21:-1])
        if close >= prior_high:
            signals.append(Signal("UP", _confidence(close - prior_high, atr14), "twenty-candle upside breakout"))
        elif close <= prior_low:
            signals.append(Signal("DOWN", _confidence(prior_low - close, atr14), "twenty-candle downside breakout"))
        else:
            signals.append(Signal("ABSTAIN", 0.0, "inside recent range"))

    if len(volumes) >= 21:
        avg_volume = sum(volumes[-21:-1]) / 20
        if avg_volume > 0 and volumes[-1] > avg_volume * 1.15:
            if close > open_:
                signals.append(Signal("UP", _confidence(volumes[-1] / avg_volume - 1, 0.8), "high-volume green candle"))
            elif close < open_:
                signals.append(Signal("DOWN", _confidence(volumes[-1] / avg_volume - 1, 0.8), "high-volume red candle"))
        else:
            signals.append(Signal("ABSTAIN", 0.0, "volume unremarkable"))

    if sma20 is not None:
        if close > sma20:
            signals.append(Signal("UP", _confidence(close - sma20, atr14 * 2), "close above sma20"))
        elif close < sma20:
            signals.append(Signal("DOWN", _confidence(sma20 - close, atr14 * 2), "close below sma20"))

    return signals


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = 0.0
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_dd = min(max_dd, value - peak)
    return max_dd


_INTERVAL_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720, "1d": 1440,
}


async def run_backtest(
    *,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    lookback: int = 240,
    horizon_minutes: int = 60,
    threshold_bps: float = 0.0,
    fee_bps: float = 0.0,
) -> dict[str, Any]:
    """Run a deterministic historical harness over recent Binance candles.

    Default: interval=1h with horizon=1 candle (1 hour ahead).
    """
    if lookback < 20:
        raise ValueError("lookback must be at least 20")
    if horizon_minutes < 1:
        raise ValueError("horizon_minutes must be at least 1")
    if threshold_bps < 0 or fee_bps < 0:
        raise ValueError("threshold_bps and fee_bps cannot be negative")
    interval = interval.lower()
    if interval not in _INTERVAL_MINUTES:
        raise ValueError(f"unsupported interval {interval}")

    interval_min = _INTERVAL_MINUTES[interval]
    horizon_periods = max(1, round(horizon_minutes / interval_min))
    effective_horizon_min = horizon_periods * interval_min

    limit = min(_MAX_BINANCE_LIMIT, lookback + horizon_periods + _WARMUP_CANDLES)
    candles = await _fetch_klines(symbol.upper(), interval, limit)
    if len(candles) < _WARMUP_CANDLES + horizon_periods + 1:
        raise ValueError("not enough candles returned for backtest")

    start_idx = max(_WARMUP_CANDLES, len(candles) - lookback - horizon_periods)
    end_idx = len(candles) - horizon_periods

    rows: list[dict[str, Any]] = []
    equity_curve: list[float] = []
    cumulative_return = 0.0
    wins = losses = flat = skipped = directional_trades = 0
    gross_profit = 0.0
    gross_loss = 0.0
    prediction_counts = {"UP": 0, "DOWN": 0, "TIE": 0}

    for idx in range(start_idx, end_idx):
        window = candles[: idx + 1]
        entry = candles[idx]["close"]
        target = candles[idx + horizon_periods]["close"]
        move_bps = (target - entry) / entry * 10_000 if entry else 0.0

        if move_bps > threshold_bps:
            actual = "UP"
        elif move_bps < -threshold_bps:
            actual = "DOWN"
        else:
            actual = "TIE"
            flat += 1

        aggregate = _vote_from_signals(_technical_signals(window))
        prediction = aggregate["final_prediction"]
        prediction_counts[prediction] += 1

        if prediction == "UP":
            return_bps = move_bps - fee_bps
        elif prediction == "DOWN":
            return_bps = -move_bps - fee_bps
        else:
            return_bps = 0.0
            skipped += 1

        if prediction in ("UP", "DOWN"):
            directional_trades += 1
            is_correct = prediction == actual if actual in ("UP", "DOWN") else None
            if is_correct is True:
                wins += 1
            elif is_correct is False:
                losses += 1

            if return_bps > 0:
                gross_profit += return_bps
            elif return_bps < 0:
                gross_loss += abs(return_bps)
        else:
            is_correct = None

        cumulative_return += return_bps
        equity_curve.append(round(cumulative_return, 4))

        rows.append(
            {
                "time": _ms_to_iso(candles[idx]["close_time"]),
                "target_time": _ms_to_iso(candles[idx + horizon_periods]["close_time"]),
                "entry_price": round(entry, 2),
                "target_price": round(target, 2),
                "move_bps": round(move_bps, 2),
                "return_bps": round(return_bps, 2),
                "prediction": prediction,
                "actual": actual,
                "is_correct": is_correct,
                "up_votes": aggregate["up_votes"],
                "down_votes": aggregate["down_votes"],
                "abstain_votes": aggregate["abstain_votes"],
                "avg_confidence": aggregate["avg_confidence"],
                "equity_bps": round(cumulative_return, 2),
            }
        )

    scored_predictions = wins + losses
    trades = directional_trades
    evaluated = len(rows)
    accuracy = wins / scored_predictions if scored_predictions else None
    coverage = trades / evaluated if evaluated else 0.0
    avg_return = cumulative_return / trades if trades else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss else None

    return {
        "config": {
            "symbol": symbol.upper(),
            "interval": interval,
            "lookback": lookback,
            "horizon_minutes": effective_horizon_min,
            "horizon_periods": horizon_periods,
            "threshold_bps": threshold_bps,
            "fee_bps": fee_bps,
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "candles_evaluated": evaluated,
        "trades": trades,
        "scored_predictions": scored_predictions,
        "skipped": skipped,
        "wins": wins,
        "losses": losses,
        "flat_actuals": flat,
        "accuracy": accuracy,
        "coverage": coverage,
        "avg_return_bps": round(avg_return, 4),
        "cumulative_return_bps": round(cumulative_return, 4),
        "max_drawdown_bps": round(_max_drawdown(equity_curve), 4),
        "profit_factor": None if profit_factor is None else round(profit_factor, 4),
        "prediction_counts": prediction_counts,
        "rows": rows[-100:],
    }
