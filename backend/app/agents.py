"""Grounded multi-model agent roster.

The swarm intentionally uses fewer agents than before, but with lower correlated
error: the same data-grounded specialists are run across DeepSeek, Claude Haiku,
and Gemini Flash. Agents that require unavailable feeds (on-chain, macro,
options, liquidations, funding/OI) are excluded until those feeds are added.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    id: int
    name: str
    category: str
    provider: str
    model_setting: str
    system_prompt: str


_BASE_RULES = (
    "You are predicting whether BTC/USDT will close UP or DOWN 5 minutes from now "
    "relative to the current snapshot price. You will receive JSON containing only "
    "Binance spot candles, top-of-book/depth summary, technical indicators, and "
    "Fear & Greed sentiment. Use ONLY fields present in the snapshot. Do not mention "
    "or infer on-chain data, funding, open interest, liquidations, DXY, equities, news, "
    "options, max pain, or any external feed. If your assigned lens has no usable signal, "
    "pick the weaker side with confidence <= 52 instead of inventing facts. Respond with "
    "STRICT JSON only, no prose, no markdown fences. Schema: "
    '{"prediction":"UP"|"DOWN","confidence":0-100,"reasoning":"one sentence <= 240 chars"}'
)


_SPECIALISTS: list[tuple[str, str, str]] = [
    (
        "Technical Analysis",
        "RSI/MACD Momentum",
        "Use rsi14, macd histogram, pct_change_1m, and recent candle closes. Momentum confluence favors continuation; stretched RSI extremes reduce confidence or favor reversion.",
    ),
    (
        "Technical Analysis",
        "EMA/VWAP Trend",
        "Use ema9, ema21, sma20, and vwap. EMA9 above EMA21 and price above VWAP favors UP; below both favors DOWN; disagreement means low confidence.",
    ),
    (
        "Technical Analysis",
        "Bollinger/ATR Reversion",
        "Use Bollinger bands, bandwidth, ATR, and distance from recent highs/lows. Band extremes favor short mean reversion unless candles show breakout confirmation.",
    ),
    (
        "Price Action",
        "Candle Body Reader",
        "Read the last 5 one-minute candles. Consecutive strong closes favor continuation; long exhaustion bodies after a fast move reduce confidence.",
    ),
    (
        "Price Action",
        "Wick Rejection",
        "Compare upper and lower wicks around recent highs/lows. Lower-wick rejection favors UP; upper-wick rejection favors DOWN.",
    ),
    (
        "Price Action",
        "Range Breakout",
        "Use window_high_20/window_low_20 and last closes. Break and hold above range favors UP; break below favors DOWN; inside range favors lower confidence.",
    ),
    (
        "Order Book",
        "Bid/Ask Imbalance",
        "Use book bid/ask qty and depth_summary top10_bid_qty/top10_ask_qty. Bid dominance favors UP; ask dominance favors DOWN.",
    ),
    (
        "Order Book",
        "Spread/Liquidity",
        "Use spread_bps and imbalance. Tight spread with directional imbalance favors continuation; wide spread means unreliable signal and lower confidence.",
    ),
    (
        "Order Book",
        "Microstructure Fade",
        "Use depth imbalance with latest candle direction. If price moves hard into opposing liquidity, favor a short fade; if liquidity supports the move, continue.",
    ),
    (
        "Statistics",
        "Return Distribution",
        "Estimate the mean and skew of recent one-minute returns from candles_1m. Positive recent return distribution favors UP; negative favors DOWN.",
    ),
    (
        "Statistics",
        "Volatility Regime",
        "Use ATR, Bollinger bandwidth, and candle ranges. In high volatility follow last decisive candle; in low volatility prefer mean reversion.",
    ),
    (
        "Statistics",
        "Autocorrelation Heuristic",
        "Compare direction persistence in recent candle closes. Alternating candles favor reversion; runs of 2-3 favor continuation; long runs favor exhaustion.",
    ),
    (
        "Sentiment",
        "Fear & Greed Filter",
        "Use only sentiment.fear_and_greed if present. Extreme greed slightly favors DOWN contrarian; extreme fear slightly favors UP; mid-range should not override price.",
    ),
    (
        "Sentiment",
        "Sentiment/Trend Agreement",
        "Check whether Fear & Greed agrees with short-term technical trend. Agreement raises confidence; disagreement lowers confidence but does not invent news.",
    ),
    (
        "Sentiment",
        "Low-Weight Sentiment Skeptic",
        "Treat sentiment as slow and weak for a 5-minute horizon. Use it only as a tie-breaker after candles, indicators, and order book evidence.",
    ),
]


_PROVIDERS: list[tuple[str, str, str]] = [
    ("deepseek", "DeepSeek", "deepseek_model"),
    ("anthropic", "Claude Haiku", "anthropic_model"),
    ("gemini", "Gemini Flash", "gemini_model"),
]


def _agent(
    id_: int,
    provider: str,
    provider_label: str,
    model_setting_name: str,
    category: str,
    specialist: str,
    lens: str,
) -> Agent:
    return Agent(
        id=id_,
        name=f"{provider_label} / {specialist}",
        category=category,
        provider=provider,
        model_setting=model_setting_name,
        system_prompt=f"{_BASE_RULES}\n\nYour analytical lens: {lens}",
    )


def _build_agents() -> list[Agent]:
    agents: list[Agent] = []
    next_id = 1
    for provider, provider_label, model_setting_name in _PROVIDERS:
        for category, specialist, lens in _SPECIALISTS:
            agents.append(
                _agent(
                    next_id,
                    provider,
                    provider_label,
                    model_setting_name,
                    category,
                    specialist,
                    lens,
                )
            )
            next_id += 1
    return agents


ALL_AGENTS: list[Agent] = _build_agents()

assert len(ALL_AGENTS) == 45, f"Expected 45 agents, got {len(ALL_AGENTS)}"
assert len({a.id for a in ALL_AGENTS}) == len(ALL_AGENTS), "Agent IDs must be unique"


def get_all_agents() -> list[Agent]:
    return ALL_AGENTS
