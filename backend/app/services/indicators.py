"""Pure-numpy technical indicators (RSI, EMA, MACD, Bollinger, ATR)."""

from __future__ import annotations

from typing import Iterable

import numpy as np


def _to_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr


def ema(values: Iterable[float], period: int) -> float | None:
    arr = _to_array(values)
    if arr.size < period:
        return None
    k = 2.0 / (period + 1)
    e = arr[0]
    for v in arr[1:]:
        e = v * k + e * (1 - k)
    return float(e)


def sma(values: Iterable[float], period: int) -> float | None:
    arr = _to_array(values)
    if arr.size < period:
        return None
    return float(arr[-period:].mean())


def rsi(values: Iterable[float], period: int = 14) -> float | None:
    arr = _to_array(values)
    if arr.size < period + 1:
        return None
    deltas = np.diff(arr)
    gains = np.clip(deltas, 0, None)
    losses = -np.clip(deltas, None, 0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def macd(values: Iterable[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    arr = _to_array(values)
    if arr.size < slow + signal:
        return {"macd": None, "signal": None, "histogram": None}
    # full-series EMA for line + signal
    def _series_ema(a: np.ndarray, p: int) -> np.ndarray:
        k = 2.0 / (p + 1)
        out = np.empty_like(a)
        out[0] = a[0]
        for i in range(1, a.size):
            out[i] = a[i] * k + out[i - 1] * (1 - k)
        return out

    fast_e = _series_ema(arr, fast)
    slow_e = _series_ema(arr, slow)
    macd_line = fast_e - slow_e
    signal_line = _series_ema(macd_line, signal)
    hist = macd_line - signal_line
    return {
        "macd": float(macd_line[-1]),
        "signal": float(signal_line[-1]),
        "histogram": float(hist[-1]),
    }


def bollinger(values: Iterable[float], period: int = 20, mult: float = 2.0) -> dict:
    arr = _to_array(values)
    if arr.size < period:
        return {"upper": None, "middle": None, "lower": None, "bandwidth": None}
    window = arr[-period:]
    mean = float(window.mean())
    std = float(window.std(ddof=0))
    upper = mean + mult * std
    lower = mean - mult * std
    bandwidth = (upper - lower) / mean if mean else None
    return {"upper": upper, "middle": mean, "lower": lower, "bandwidth": bandwidth}


def atr(highs: Iterable[float], lows: Iterable[float], closes: Iterable[float], period: int = 14) -> float | None:
    h = _to_array(highs)
    l = _to_array(lows)
    c = _to_array(closes)
    if h.size < period + 1:
        return None
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return float(tr[-period:].mean())


def vwap(highs: Iterable[float], lows: Iterable[float], closes: Iterable[float], volumes: Iterable[float]) -> float | None:
    h = _to_array(highs)
    l = _to_array(lows)
    c = _to_array(closes)
    v = _to_array(volumes)
    if h.size == 0 or v.sum() == 0:
        return None
    typical = (h + l + c) / 3.0
    return float((typical * v).sum() / v.sum())
