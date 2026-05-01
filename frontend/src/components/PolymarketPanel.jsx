export default function PolymarketPanel({ markets }) {
  return (
    <div className="rounded-xl bg-card p-6 border border-slate-800">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-wider text-slate-400">Polymarket — BTC short-term markets</div>
        <a
          href="https://polymarket.com/markets/crypto"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-accent hover:underline"
        >
          open ↗
        </a>
      </div>

      {(!markets || markets.length === 0) && (
        <div className="text-sm text-slate-500">
          No active BTC up/down markets returned right now. Visit Polymarket directly to view live odds.
        </div>
      )}

      <ul className="divide-y divide-slate-800">
        {(markets || []).slice(0, 6).map((m) => {
          let prices = m.outcome_prices
          if (typeof prices === 'string') {
            try { prices = JSON.parse(prices) } catch { /* keep raw */ }
          }
          let outcomes = m.outcomes
          if (typeof outcomes === 'string') {
            try { outcomes = JSON.parse(outcomes) } catch { /* keep raw */ }
          }
          return (
            <li key={m.id} className="py-2">
              <a
                href={m.url || `https://polymarket.com/event/${m.slug}`}
                target="_blank"
                rel="noreferrer"
                className="block hover:bg-slate-900/40 -mx-2 px-2 py-1 rounded"
              >
                <div className="text-sm text-slate-100 line-clamp-2">{m.question}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-400">
                  {Array.isArray(outcomes) && Array.isArray(prices) &&
                    outcomes.map((o, i) => (
                      <span key={i} className="font-mono">
                        {o}: {prices[i] ? (Number(prices[i]) * 100).toFixed(1) + '¢' : '-'}
                      </span>
                    ))}
                  {m.volume && <span>vol ${Number(m.volume).toLocaleString()}</span>}
                  {m.end_date && <span>ends {new Date(m.end_date).toLocaleDateString()}</span>}
                </div>
              </a>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
