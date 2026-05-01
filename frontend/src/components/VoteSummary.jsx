export default function VoteSummary({ prediction }) {
  if (!prediction) {
    return (
      <div className="rounded-xl bg-card p-6 border border-slate-800">
        <div className="text-slate-400 text-sm">Waiting for first prediction round…</div>
      </div>
    )
  }
  const total = (prediction.up_votes ?? 0) + (prediction.down_votes ?? 0) + (prediction.abstain_votes ?? 0)
  const up = prediction.up_votes
  const down = prediction.down_votes
  const upPct = total ? (up / total) * 100 : 0
  const downPct = total ? (down / total) * 100 : 0
  const winner = prediction.final_prediction
  return (
    <div className="rounded-xl bg-card p-6 border border-slate-800">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400">Swarm decision</div>
          <div className={`text-4xl font-bold ${winner === 'UP' ? 'text-emerald-400' : winner === 'DOWN' ? 'text-rose-400' : 'text-slate-300'}`}>
            {winner}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wider text-slate-400">Avg confidence</div>
          <div className="text-2xl font-mono">{prediction.avg_confidence?.toFixed(1)}%</div>
        </div>
      </div>

      <div className="mt-5">
        <div className="flex h-3 rounded-full overflow-hidden bg-slate-800">
          <div className="bg-emerald-500" style={{ width: `${upPct}%` }} />
          <div className="bg-rose-500" style={{ width: `${downPct}%` }} />
        </div>
        <div className="mt-2 flex justify-between text-sm">
          <div className="text-emerald-400">UP {up} ({upPct.toFixed(0)}%)</div>
          <div className="text-slate-500">Abstain {prediction.abstain_votes}</div>
          <div className="text-rose-400">DOWN {down} ({downPct.toFixed(0)}%)</div>
        </div>
      </div>
    </div>
  )
}
