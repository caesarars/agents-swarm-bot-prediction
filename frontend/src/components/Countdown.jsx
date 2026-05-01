import { useEffect, useState } from 'react'

function fmt(ms) {
  if (ms < 0) ms = 0
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function Countdown({ targetAt, label = 'Resolves in' }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(t)
  }, [])
  if (!targetAt) {
    return (
      <div className="text-slate-500 text-sm">No active round yet</div>
    )
  }
  const target = new Date(targetAt).getTime()
  const remaining = target - now
  return (
    <div className="flex flex-col items-start">
      <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
      <div className="text-3xl font-mono font-semibold text-accent">{fmt(remaining)}</div>
    </div>
  )
}
