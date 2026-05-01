function badge(text, kind) {
  const cls =
    kind === 'UP'
      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
      : kind === 'DOWN'
      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
      : 'bg-slate-700/40 text-slate-300 border border-slate-600'
  return <span className={`px-2 py-0.5 rounded text-xs font-mono ${cls}`}>{text}</span>
}

function fmtTime(s) {
  if (!s) return '-'
  return new Date(s).toLocaleTimeString()
}

export default function HistoryTable({ rows }) {
  return (
    <div className="rounded-xl bg-card border border-slate-800 overflow-hidden">
      <div className="px-6 py-4 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
        Recent rounds
      </div>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400 text-xs uppercase tracking-wider bg-slate-900/40">
            <tr>
              <th className="text-left px-4 py-2">Time</th>
              <th className="text-left px-4 py-2">Predicted</th>
              <th className="text-left px-4 py-2">Actual</th>
              <th className="text-right px-4 py-2">UP</th>
              <th className="text-right px-4 py-2">DOWN</th>
              <th className="text-right px-4 py-2">Conf</th>
              <th className="text-right px-4 py-2">Entry</th>
              <th className="text-right px-4 py-2">Settle</th>
              <th className="text-right px-4 py-2">Hit</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-800 hover:bg-slate-900/40">
                <td className="px-4 py-2 text-slate-400">{fmtTime(r.created_at)}</td>
                <td className="px-4 py-2">{badge(r.final_prediction, r.final_prediction)}</td>
                <td className="px-4 py-2">
                  {r.actual_outcome ? badge(r.actual_outcome, r.actual_outcome) : <span className="text-slate-500">pending</span>}
                </td>
                <td className="px-4 py-2 text-right text-emerald-400 font-mono">{r.up_votes}</td>
                <td className="px-4 py-2 text-right text-rose-400 font-mono">{r.down_votes}</td>
                <td className="px-4 py-2 text-right font-mono">{r.avg_confidence?.toFixed(0)}</td>
                <td className="px-4 py-2 text-right font-mono">{r.btc_price_at_predict?.toFixed(2)}</td>
                <td className="px-4 py-2 text-right font-mono">
                  {r.btc_price_at_target ? r.btc_price_at_target.toFixed(2) : '-'}
                </td>
                <td className="px-4 py-2 text-right">
                  {r.is_correct === 1 ? (
                    <span className="text-emerald-400">✓</span>
                  ) : r.is_correct === 0 ? (
                    <span className="text-rose-400">✗</span>
                  ) : (
                    <span className="text-slate-600">·</span>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-slate-500">
                  No history yet — kick off the first round.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
