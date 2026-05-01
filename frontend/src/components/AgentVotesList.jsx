import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function AgentVotesList({ predictionId }) {
  const [votes, setVotes] = useState([])
  const [filter, setFilter] = useState('ALL')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!predictionId) return
    setLoading(true)
    api.votes(predictionId)
      .then(setVotes)
      .catch(() => setVotes([]))
      .finally(() => setLoading(false))
  }, [predictionId])

  const filtered = filter === 'ALL' ? votes : votes.filter((v) => v.vote === filter)

  return (
    <div className="rounded-xl bg-card border border-slate-800">
      <div className="px-6 py-4 flex items-center justify-between border-b border-slate-800">
        <div className="text-xs uppercase tracking-wider text-slate-400">
          Per-agent votes {predictionId ? `(round #${predictionId})` : ''}
        </div>
        <div className="flex gap-2 text-xs">
          {['ALL', 'UP', 'DOWN', 'ABSTAIN'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-1 rounded ${
                filter === f ? 'bg-accent text-slate-900 font-semibold' : 'bg-slate-800 text-slate-300'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="max-h-[420px] overflow-auto divide-y divide-slate-800">
        {loading && <div className="px-6 py-3 text-slate-500 text-sm">Loading…</div>}
        {!loading && filtered.length === 0 && (
          <div className="px-6 py-3 text-slate-500 text-sm">No votes to show.</div>
        )}
        {filtered.map((v) => (
          <div key={v.agent_id} className="px-6 py-3 grid grid-cols-12 gap-3 items-start text-sm">
            <div className="col-span-1 text-slate-500 font-mono">#{v.agent_id}</div>
            <div className="col-span-3">
              <div className="text-slate-100">{v.agent_name}</div>
              <div className="text-xs text-slate-500">{v.agent_category}</div>
            </div>
            <div className="col-span-1">
              <span
                className={`px-2 py-0.5 rounded text-xs font-mono ${
                  v.vote === 'UP'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : v.vote === 'DOWN'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                    : 'bg-slate-700/40 text-slate-300 border border-slate-600'
                }`}
              >
                {v.vote}
              </span>
            </div>
            <div className="col-span-1 font-mono text-slate-300">{v.confidence?.toFixed(0)}%</div>
            <div className="col-span-6 text-slate-300/80">{v.reasoning || (v.error ? <span className="text-rose-400">err: {v.error}</span> : '-')}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
