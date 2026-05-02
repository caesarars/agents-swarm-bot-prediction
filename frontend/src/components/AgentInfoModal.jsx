import { useEffect, useRef } from 'react'

function pct(correct, total) {
  if (!total) return '-'
  return `${((correct / total) * 100).toFixed(1)}%`
}

function weight(value) {
  if (value === undefined || value === null) return '1.00'
  return Number(value).toFixed(2)
}

const CATEGORY_COLORS = {
  'Technical Analysis': 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  'Price Action': 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  'Order Book': 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  'Futures': 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  'Statistics': 'bg-pink-500/20 text-pink-300 border-pink-500/40',
  'Sentiment': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
}

const PROVIDER_COLORS = {
  deepseek: 'text-orange-300',
  anthropic: 'text-violet-300',
  gemini: 'text-teal-300',
}

function Avatar({ name, id }) {
  const hue = ((id || 0) * 137) % 360
  const initial = (name || '?').charAt(0).toUpperCase()
  return (
    <div
      className="w-14 h-14 rounded-xl flex items-center justify-center text-xl font-bold text-white shadow-lg shrink-0"
      style={{ background: `linear-gradient(135deg, hsl(${hue}, 70%, 55%), hsl(${hue}, 70%, 35%))` }}
    >
      {initial}
    </div>
  )
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
  const categoryClass = CATEGORY_COLORS[row.category] || 'bg-slate-800 text-slate-300 border-slate-700'
  const providerClass = PROVIDER_COLORS[meta.provider || row.provider] || 'text-slate-300'

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose()
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl overflow-hidden">
        {/* Identity Header */}
        <div className="px-6 py-6 border-b border-slate-800 flex items-center gap-4">
          <Avatar name={row.name} id={Number(row.id)} />
          <div className="min-w-0">
            <div className="text-base font-bold text-slate-100 truncate">{row.name}</div>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${categoryClass}`}>
                {row.category}
              </span>
              <span className={`text-xs font-mono font-medium ${providerClass}`}>
                {meta.provider || row.provider || '-'}
              </span>
              <span className="text-xs text-slate-500 font-mono">
                {meta.model || '-'}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-auto text-slate-500 hover:text-slate-200 transition-colors shrink-0"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Role / Identity */}
        <div className="px-6 py-5">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2 font-semibold">Bot Identity — Role & Function</div>
          <p className="text-sm text-slate-300 leading-relaxed">{role}</p>
        </div>

        {/* Performance Stats */}
        <div className="px-6 pb-5">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-3 font-semibold">Swarm Performance</div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl bg-slate-950/50 border border-slate-800 p-3 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Accuracy</div>
              <div className="text-xl font-bold font-mono text-slate-100">{pct(row.correct, row.total)}</div>
            </div>
            <div className="rounded-xl bg-slate-950/50 border border-slate-800 p-3 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Calls</div>
              <div className="text-xl font-bold font-mono text-slate-100">{row.correct ?? 0}<span className="text-slate-600 text-sm">/{row.total ?? 0}</span></div>
            </div>
            <div className="rounded-xl bg-slate-950/50 border border-slate-800 p-3 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Weight</div>
              <div className={`text-xl font-bold font-mono ${(row.weight ?? 1) >= 1 ? 'text-emerald-400' : 'text-rose-300'}`}>
                {weight(row.weight)}<span className="text-slate-500 text-sm">x</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/30 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-lg bg-accent text-slate-900 text-sm font-bold hover:opacity-90 transition-opacity"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
