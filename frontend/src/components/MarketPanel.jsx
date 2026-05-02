function row(label, value, hint) {
  return (
    <div className="flex justify-between text-sm py-1">
      <span className="text-slate-400">{label}</span>
      <span className="font-mono text-slate-100">
        {value}
        {hint && <span className="text-slate-500 ml-2 text-xs">{hint}</span>}
      </span>
    </div>
  )
}

function fmt(n, d = 2) {
  if (n === null || n === undefined) return '-'
  return Number(n).toFixed(d)
}

export default function MarketPanel({ snapshot, status }) {
  if (!snapshot) {
    return (
      <div className="rounded-xl bg-card p-6 border border-slate-800">
        <div className="text-slate-500 text-sm">Loading market…</div>
      </div>
    )
  }
  const ind = snapshot.indicators || {}
  const macd = ind.macd || {}
  const boll = ind.bollinger || {}
  const fng = snapshot.sentiment?.fear_and_greed
  const futures = snapshot.futures || {}
  return (
    <div className="rounded-xl bg-card p-6 border border-slate-800">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-wider text-slate-400">BTC/USDT — Binance</div>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            status === 'ok'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
          }`}
        >
          {status === 'ok' ? 'live' : 'stale'}
        </span>
      </div>
      <div className="text-3xl font-bold font-mono">${fmt(snapshot.price, 2)}</div>
      <div className={`text-sm font-mono ${snapshot.pct_change_24h >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
        24h {fmt(snapshot.pct_change_24h, 2)}% &middot; 15m {fmt(snapshot.pct_change_15m, 3)}% &middot; 5m {fmt(snapshot.pct_change_5m, 3)}%
      </div>

      <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-1">
        {row('RSI(14)', fmt(ind.rsi14, 1))}
        {row('EMA9 / EMA21', `${fmt(ind.ema9)} / ${fmt(ind.ema21)}`)}
        {row('MACD hist', fmt(macd.histogram, 3))}
        {row('Boll BW', fmt(boll.bandwidth, 4))}
        {row('ATR(14)', fmt(ind.atr14, 2))}
        {row('VWAP', fmt(ind.vwap, 2))}
        {row('Futures premium', futures.available ? `${fmt(futures.premium_bps, 2)} bps` : '-')}
        {row('Funding', futures.available && futures.last_funding_rate != null ? `${fmt(futures.last_funding_rate * 100, 4)}%` : '-')}
        {row('Open interest', futures.available && futures.open_interest != null ? Number(futures.open_interest).toLocaleString() : '-')}
        {row(
          'Spread',
          snapshot.depth_summary?.spread_bps ? `${fmt(snapshot.depth_summary.spread_bps, 2)} bps` : '-',
          snapshot.depth_summary?.imbalance ? `imb ${(snapshot.depth_summary.imbalance * 100).toFixed(1)}%` : '',
        )}
        {row('Fear & Greed', fng ? `${fng.value} (${fng.classification})` : '-')}
      </div>
    </div>
  )
}
