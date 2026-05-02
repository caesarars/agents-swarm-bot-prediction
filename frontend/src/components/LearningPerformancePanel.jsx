function pct(correct, total) {
  if (!total) return '-'
  return `${((correct / total) * 100).toFixed(1)}%`
}

function weight(value) {
  if (value === undefined || value === null) return '1.00'
  return Number(value).toFixed(2)
}

function agentRows(profile, agents) {
  const byId = Object.fromEntries((agents || []).map((a) => [String(a.id), a]))
  return Object.entries(profile?.agent_stats || {})
    .map(([id, stat]) => ({
      id,
      name: byId[id]?.name || `Agent #${id}`,
      category: byId[id]?.category || '-',
      provider: byId[id]?.provider || '-',
      correct: stat.correct || 0,
      total: stat.total || 0,
      accuracy: stat.total ? stat.correct / stat.total : 0,
      weight: profile?.agent_weights?.[id] ?? 1,
    }))
    .filter((row) => row.total > 0)
}

function compactName(name) {
  return name.replace('Haiku Validator / ', 'Haiku / ')
}

export default function LearningPerformancePanel({ profile, agents }) {
  const rows = agentRows(profile, agents)
  const top = [...rows].sort((a, b) => b.weight - a.weight || b.accuracy - a.accuracy).slice(0, 6)
  const bottom = [...rows].sort((a, b) => a.weight - b.weight || a.accuracy - b.accuracy).slice(0, 6)
  const categories = Object.entries(profile?.category_stats || {}).map(([name, stat]) => ({
    name,
    correct: stat.correct || 0,
    total: stat.total || 0,
    weight: profile?.category_weights?.[name] ?? 1,
  }))

  return (
    <div className="rounded-xl bg-card border border-slate-800 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400">Learning performance</div>
          <div className="text-sm text-slate-500 mt-1">
            {profile?.settled_predictions || 0} settled rounds in learning window
          </div>
        </div>
        <span className={`text-xs px-2 py-1 rounded border ${profile?.enabled ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
          {profile?.enabled ? 'active' : 'warming up'}
        </span>
      </div>

      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Top weighted agents</div>
          <div className="space-y-2">
            {top.map((r) => (
              <div key={r.id} className="rounded-lg bg-slate-950/40 border border-slate-800 p-3">
                <div className="flex justify-between gap-3 text-sm">
                  <span className="text-slate-100 truncate">{compactName(r.name)}</span>
                  <span className="font-mono text-emerald-400">{weight(r.weight)}x</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {r.category} · {pct(r.correct, r.total)} · {r.correct}/{r.total}
                </div>
              </div>
            ))}
            {!top.length && <div className="text-sm text-slate-500">Need settled rounds before weights appear.</div>}
          </div>
        </div>

        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Lowest weighted agents</div>
          <div className="space-y-2">
            {bottom.map((r) => (
              <div key={r.id} className="rounded-lg bg-slate-950/40 border border-slate-800 p-3">
                <div className="flex justify-between gap-3 text-sm">
                  <span className="text-slate-100 truncate">{compactName(r.name)}</span>
                  <span className="font-mono text-rose-300">{weight(r.weight)}x</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {r.category} · {pct(r.correct, r.total)} · {r.correct}/{r.total}
                </div>
              </div>
            ))}
            {!bottom.length && <div className="text-sm text-slate-500">Need settled rounds before weights appear.</div>}
          </div>
        </div>

        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Category weights</div>
          <div className="space-y-2">
            {categories.map((r) => (
              <div key={r.name} className="rounded-lg bg-slate-950/40 border border-slate-800 p-3">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-100">{r.name}</span>
                  <span className="font-mono text-accent">{weight(r.weight)}x</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{pct(r.correct, r.total)} · {r.correct}/{r.total}</div>
              </div>
            ))}
            {!categories.length && <div className="text-sm text-slate-500">No category history yet.</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
