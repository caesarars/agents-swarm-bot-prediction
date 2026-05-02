"""Grounded agent roster with DeepSeek primary agents.

Agents that require unavailable feeds (on-chain, macro, options, liquidations,
funding/OI) are excluded until those feeds are added.
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
    "You are predicting whether BTC/USDT will close UP or DOWN 1 hour from now "
    "relative to the current snapshot price. You will receive JSON with these "
    "fields: price, pct_change_1h, pct_change_15m, pct_change_24h, candles_1h "
    "(last 30 hourly candles), candles_15m (last 16 fifteen-minute candles), "
    "indicators computed on 1h closes (rsi14, ema9, ema21, sma20, macd, bollinger, "
    "atr14, vwap, window_high_20, window_low_20), top-of-book/depth summary, "
    "Binance Futures data, and Fear & Greed sentiment. Use ONLY fields present "
    "in the snapshot. Do not mention or infer on-chain data, liquidations, DXY, "
    "equities, news, options, or any external feed. If your assigned lens has no "
    "usable signal, pick the weaker side with confidence <= 52 instead of inventing "
    "facts. Respond with STRICT JSON only, no prose, no markdown fences. Use this "
    'valid JSON shape: {"prediction":"UP","confidence":51,"reasoning":"one sentence <= 240 chars"}. '
    "prediction must be either UP or DOWN."
)


_SPECIALISTS: list[tuple[str, str, str]] = [
    (
        "Technical Analysis",
        "RSI/MACD Momentum",
        "Use rsi14, macd histogram, pct_change_1h, pct_change_15m, and recent candle closes. Momentum confluence favors continuation; stretched RSI extremes reduce confidence or favor reversion.",
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
        "Technical Analysis",
        "EMA Spread Strength",
        "Measure how far ema9 is from ema21 relative to atr14. A widening positive spread favors UP; widening negative spread favors DOWN; tiny spread means low confidence.",
    ),
    (
        "Technical Analysis",
        "VWAP Distance",
        "Compare price to vwap and atr14. Small distance with trend alignment favors continuation; far above vwap favors DOWN reversion; far below favors UP reversion.",
    ),
    (
        "Technical Analysis",
        "SMA20 Slope",
        "Use sma20 and recent closes to infer slope. Price above rising sma20 favors UP; below falling sma20 favors DOWN; flat slope lowers confidence.",
    ),
    (
        "Technical Analysis",
        "Bollinger Bandwidth Regime",
        "Use bollinger bandwidth. Low bandwidth means breakout risk; choose direction from last close sequence. High bandwidth means prefer reversion from band extremes.",
    ),
    (
        "Technical Analysis",
        "ATR Breakout Filter",
        "Use atr14 and latest candle range. A close beyond recent range with range above ATR favors continuation; otherwise fade weak breakouts.",
    ),
    (
        "Technical Analysis",
        "Indicator Confluence Counter",
        "Count agreement among rsi14, macd histogram, ema9/ema21, vwap, and sma20. Predict the side with the most grounded confluence.",
    ),
    (
        "Technical Analysis",
        "Short Trend Exhaustion",
        "If indicators all point one way but RSI is stretched and price is near band extreme, expect 1-hour exhaustion against the crowded direction.",
    ),
    (
        "Price Action",
        "Candle Body Reader",
        "Read the last 5 hourly candles. Consecutive strong closes favor continuation; long exhaustion bodies after a fast move reduce confidence.",
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
        "Price Action",
        "Last Candle Close Location",
        "Compare the latest close to its high-low range. Close near high favors UP; close near low favors DOWN; close near middle is neutral.",
    ),
    (
        "Price Action",
        "Three-Candle Run",
        "Inspect the last three candle bodies. Three aligned bodies favor continuation unless the third body is much larger than prior candles, which suggests exhaustion.",
    ),
    (
        "Price Action",
        "Inside Range Compression",
        "If recent candles are nested inside prior ranges, expect breakout in the direction of the preceding micro-trend; keep confidence modest.",
    ),
    (
        "Price Action",
        "Support Bounce",
        "Use window_low_20 and lower wicks. Repeated rejection near recent lows favors UP; clean close through recent lows favors DOWN.",
    ),
    (
        "Price Action",
        "Resistance Rejection",
        "Use window_high_20 and upper wicks. Repeated rejection near recent highs favors DOWN; clean close through recent highs favors UP.",
    ),
    (
        "Price Action",
        "Micro Pullback",
        "In an obvious short trend, a small counter candle after momentum usually favors trend resumption; large counter candle favors reversal.",
    ),
    (
        "Price Action",
        "Candle Volume Confirmation",
        "Use recent candle volume. Directional candles with rising volume are more credible; directional candles on fading volume are less credible.",
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
        "Order Book",
        "Top-10 Depth Pressure",
        "Compare top10_bid_qty and top10_ask_qty. Persistent bid pressure favors UP; persistent ask pressure favors DOWN; small difference means neutral.",
    ),
    (
        "Order Book",
        "Book vs Candle Divergence",
        "If candles rise while order book imbalance leans ask-heavy, suspect fade DOWN. If candles fall while bid-heavy, suspect bounce UP.",
    ),
    (
        "Order Book",
        "Spread Risk Guard",
        "If spread_bps is elevated, lower confidence and avoid strong continuation calls. If spread is tight, trust depth imbalance more.",
    ),
    (
        "Order Book",
        "Best Bid Ask Skew",
        "Use best_bid/best_ask and bid_qty/ask_qty. Larger size at best bid favors UP; larger size at best ask favors DOWN.",
    ),
    (
        "Order Book",
        "Liquidity Cushion",
        "If bid depth is large below price, downside is cushioned and UP is favored. If ask depth is large above price, upside is capped and DOWN is favored.",
    ),
    (
        "Order Book",
        "Thin Book Continuation",
        "When both sides have low top10 depth, price can continue the latest candle direction easily; lower confidence because slippage risk is high.",
    ),
    (
        "Order Book",
        "Depth Neutral Arbiter",
        "If book imbalance is near zero, ignore order book and choose direction from price action with low-to-medium confidence.",
    ),
    (
        "Futures",
        "Funding Rate Contrarian",
        "Use futures.last_funding_rate. Strong positive funding means crowded longs and favors DOWN if spot is stretched; negative funding favors UP if spot is stabilizing.",
    ),
    (
        "Futures",
        "Premium Index Momentum",
        "Use futures.premium_bps and mark/index price. Positive premium expanding with spot momentum favors UP; premium collapsing favors DOWN.",
    ),
    (
        "Futures",
        "Open Interest Pressure",
        "Use futures.open_interest as context with recent candle direction. Rising OI with price up favors UP continuation; rising OI with price down favors DOWN continuation.",
    ),
    (
        "Futures",
        "Mark vs Index Skew",
        "Compare mark_price and index_price. Mark above index with weak spot candles warns of long crowding; mark below index with firm spot warns of short crowding.",
    ),
    (
        "Futures",
        "Funding History Slope",
        "Use recent_funding_rates. Funding becoming more positive can signal overheated longs; funding becoming less positive or negative can support UP.",
    ),
    (
        "Futures",
        "Perp Spot Agreement",
        "When futures premium and spot technical trend agree, raise confidence in continuation. When they disagree, lower confidence or favor mean reversion.",
    ),
    (
        "Futures",
        "Next Funding Proximity",
        "Use next_funding_time. If funding is extreme near the funding timestamp, expect positioning effects; otherwise keep futures weight modest.",
    ),
    (
        "Futures",
        "Crowding Reversal",
        "Look for high funding plus stretched RSI/Bollinger as crowded long risk favoring DOWN, or negative funding plus oversold spot as crowded short risk favoring UP.",
    ),
    (
        "Futures",
        "Futures Confidence Gate",
        "If futures.available is false, ignore futures. If available, use futures only when premium, funding, and spot trend point to the same side.",
    ),
    (
        "Futures",
        "Derivative Tie Breaker",
        "Use futures data only as a tie breaker when technical, price action, and order book votes are balanced. Avoid overriding clear spot evidence.",
    ),
    (
        "Statistics",
        "Return Distribution",
        "Estimate the mean and skew of recent hourly returns from candles_1h. Positive recent return distribution favors UP; negative favors DOWN.",
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
        "Statistics",
        "Mean Reversion Z-Score",
        "Estimate price z-score against recent closes. Large positive deviation favors DOWN; large negative deviation favors UP; near mean follows weak trend.",
    ),
    (
        "Statistics",
        "Recent Hit-Rate Policy",
        "Imagine following the previous candle for the recent window. If that policy would have worked, follow last candle; otherwise oppose it.",
    ),
    (
        "Statistics",
        "Range Percentile",
        "Compare latest price to the recent high-low percentile. Near top favors DOWN unless breakout is strong; near bottom favors UP unless breakdown is strong.",
    ),
    (
        "Statistics",
        "Volume-Weighted Drift",
        "Weight recent candle returns by volume. Positive volume-weighted drift favors UP; negative volume-weighted drift favors DOWN.",
    ),
    (
        "Statistics",
        "Volatility Compression",
        "If recent ranges are compressed, expect a directional move using last micro-trend. If ranges are expanded, expect reversion unless breakout holds.",
    ),
    (
        "Statistics",
        "Hour Proxy Slope",
        "Use the last 4 candles_15m closes as a fine-grained proxy for the next hour. Positive slope favors UP; negative slope favors DOWN.",
    ),
    (
        "Statistics",
        "Robust Median Return",
        "Use median rather than mean of recent returns to reduce outlier influence. Positive median favors UP; negative median favors DOWN.",
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
        "Sentiment is slow but at a 1-hour horizon it carries some weight. Use it as a moderate-weight tie-breaker after candles, indicators, and order book evidence.",
    ),
    (
        "Sentiment",
        "Extreme Greed Contrarian",
        "If Fear & Greed is extreme greed, reduce bullish confidence and prefer DOWN only when technicals are also stretched.",
    ),
    (
        "Sentiment",
        "Extreme Fear Contrarian",
        "If Fear & Greed is extreme fear, reduce bearish confidence and prefer UP only when price action shows stabilization.",
    ),
    (
        "Sentiment",
        "Neutral Sentiment Ignorer",
        "If Fear & Greed is neutral or missing, ignore sentiment entirely and base prediction on technical and order book evidence.",
    ),
    (
        "Sentiment",
        "Sentiment Confidence Dampener",
        "When sentiment conflicts with hourly price action, keep the price-action direction but lower confidence; do not let sentiment fully override technicals.",
    ),
    (
        "Sentiment",
        "Risk Appetite Overlay",
        "Use Fear & Greed only as a broad risk appetite overlay. Greed supports trend continuation when not extreme; fear supports caution when not extreme.",
    ),
    (
        "Sentiment",
        "Contrarian Tie Breaker",
        "When technical, price action, and order book signals are balanced, use Fear & Greed contrarian logic as the tie breaker.",
    ),
    (
        "Sentiment",
        "Sentiment Minimalist",
        "Give sentiment the smallest weight. Only let it affect the call when all market snapshot signals are weak or contradictory.",
    ),
]


def _agent(
    id_: int,
    category: str,
    specialist: str,
    lens: str,
    provider: str = "deepseek",
    provider_label: str = "",
) -> Agent:
    model_setting = "anthropic_model" if provider == "anthropic" else "deepseek_model"
    name = f"{provider_label} / {specialist}" if provider_label else specialist
    return Agent(
        id=id_,
        name=name,
        category=category,
        provider=provider,
        model_setting=model_setting,
        system_prompt=f"{_BASE_RULES}\n\nYour analytical lens: {lens}",
    )


def _build_agents() -> list[Agent]:
    agents: list[Agent] = []
    next_id = 1
    for category, specialist, lens in _SPECIALISTS:
        agents.append(
            _agent(
                next_id,
                category,
                specialist,
                lens,
            )
        )
        next_id += 1
    return agents


ALL_AGENTS: list[Agent] = _build_agents()

assert len(ALL_AGENTS) == 60, f"Expected 60 agents, got {len(ALL_AGENTS)}"
assert len({a.id for a in ALL_AGENTS}) == len(ALL_AGENTS), "Agent IDs must be unique"


def get_all_agents() -> list[Agent]:
    return ALL_AGENTS
