import { useEffect, useRef } from 'react'

function pct(correct, total) {
  if (!total) return '-'
  return `${((correct / total) * 100).toFixed(1)}%`
}

function weight(value) {
  if (value === undefined || value === null) return '1.00'
  return Number(value).toFixed(2)
}

export default function AgentInfoModal({ isOpen, onClose, row, agentMeta }) {
  const backdropRef = useRef(null)

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      document.addEventListener('keydown', onKey)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose])

  if (!isOpen || !row) return null

  const meta = agentMeta || {}
  const role = meta.role || 'No description available.'

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose()
      }}
    >
      <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-start justify-between gap-4">
          <div>
            <div className="text-lg font-semibold text-slate-100">{row.name}</div>
            <div className="text-xs text-slate-400 mt-1">
              {row.category} · {meta.provider || row.provider || '-'} · {meta.model || '-'}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-colors"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">Role & Function</div>
            <p className="text-sm text-slate-300 leading-relaxed">{role}</p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-slate-950/50 border border-slate-800 p-3 text-center">
              <div className="text-xs text-slate-500">Accuracy</div>
              <div className="text-lg font-semibold font-mono text-slate-100 mt-1">{pct(row.correct, row.total)}</div>
            </div>
            <div className="rounded-lg bg-slate-950/50 border border-slate-800 p-3 text-center">
              <div className="text-xs text-slate-500">Correct / Total</div>
              <div className="text-lg font-semibold font-mono text-slate-100 mt-1">{row.correct ?? 0} / {row.total ?? 0}</div>
            </div>
            <div className="rounded-lg bg-slate-950/50 border border-slate-800 p-3 text-center">
              <div className="text-xs text-slate-500">Weight</div>
              <div className={`text-lg font-semibold font-mono mt-1 ${(row.weight ?? 1) >= 1 ? 'text-emerald-400' : 'text-rose-300'}`}>
                {weight(row.weight)}x
              </div>
            </div>
          </div>

          <div className="rounded-lg bg-slate-800/50 border border-slate-700/50 p-3">
            <div className="text-xs text-slate-400">
              <span className="font-medium text-slate-300">How it works:</span> This AI bot receives the same market snapshot (price, indicators, order book, futures data, sentiment) as every other agent. Based on its specific analytical lens above, it independently votes UP, DOWN, or ABSTAIN with a confidence score. The swarm then aggregates all votes. Learning system adjusts this bot's weight over time based on its historical accuracy.
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/30 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm font-medium hover:bg-slate-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
