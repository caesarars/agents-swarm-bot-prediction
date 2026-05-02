import { useState } from 'react'

function pct(value, digits = 1) {
  if (value === null || value === undefined) return '-'
  return `${(Number(value) * 100).toFixed(digits)}%`
}

function bps(value, digits = 1) {
  if (value === null || value === undefined) return '-'
  return `${Number(value).toFixed(digits)} bps`
}

function metric(label, value, tone = '') {
  return (
    <div className="bg-slate-950/40 border border-slate-800 rounded-lg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-0.5 font-mono text-lg ${tone}`}>{value}</div>
    </div>
  )
}

function badge(text) {
  const cls =
    text === 'UP'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
      : text === 'DOWN'
        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
        : 'bg-slate-700/40 text-slate-300 border-slate-600'
  return <span className={`px-2 py-0.5 rounded text-xs font-mono border ${cls}`}>{text}</span>
}

export default function BacktestPanel({ result, running, error, onRun }) {
  const [form, setForm] = useState({
    interval: '15m',
    lookback: 240,
    horizon_minutes: 15,
    threshold_bps: 0,
    fee_bps: 0,
  })

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const submit = (event) => {
    event.preventDefault()
    onRun({
      interval: form.interval,
      lookback: Number(form.lookback),
      horizon_minutes: Number(form.horizon_minutes),
      threshold_bps: Number(form.threshold_bps),
      fee_bps: Number(form.fee_bps),
    })
  }

  const rows = result?.rows || []
  const cumulativeTone =
    result?.cumulative_return_bps > 0
      ? 'text-emerald-400'
      : result?.cumulative_return_bps < 0
        ? 'text-rose-400'
        : 'text-slate-100'

  return (
    <div className="rounded-xl bg-card border border-slate-800 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-800 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400">Backtesting harness</div>
          <div className="text-sm text-slate-500 mt-1">Historical Binance candles, deterministic technical-signal proxy.</div>
        </div>
        <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <label className="text-xs text-slate-400">
            Interval
            <select
              value={form.interval}
              onChange={(e) => update('interval', e.target.value)}
              className="mt-1 w-full rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 text-sm text-slate-100"
            >
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="text-xs text-slate-400">
            Lookback
            <input
              type="number"
              min="20"
              max="900"
              value={form.lookback}
              onChange={(e) => update('lookback', e.target.value)}
              className="mt-1 w-full rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 text-sm text-slate-100"
            />
          </label>
          <label className="text-xs text-slate-400">
            Horizon (min)
            <input
              type="number"
              min="1"
              max="1440"
              value={form.horizon_minutes}
              onChange={(e) => update('horizon_minutes', e.target.value)}
              className="mt-1 w-full rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 text-sm text-slate-100"
            />
          </label>
          <label className="text-xs text-slate-400">
            Threshold
            <input
              type="number"
              min="0"
              max="100"
              step="0.5"
              value={form.threshold_bps}
              onChange={(e) => update('threshold_bps', e.target.value)}
              className="mt-1 w-full rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 text-sm text-slate-100"
            />
          </label>
          <label className="text-xs text-slate-400">
            Fee
            <input
              type="number"
              min="0"
              max="100"
              step="0.5"
              value={form.fee_bps}
              onChange={(e) => update('fee_bps', e.target.value)}
              className="mt-1 w-full rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 text-sm text-slate-100"
            />
          </label>
          <button
            type="submit"
            disabled={running}
            className="self-end rounded-lg bg-accent text-slate-900 px-3 py-2 text-sm font-semibold disabled:opacity-50"
          >
            {running ? 'Running...' : 'Run'}
          </button>
        </form>
      </div>

      {error && <div className="mx-6 mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{error}</div>}

      <div className="p-6 space-y-5">
        {!result && !running && !error && <div className="text-sm text-slate-500">No backtest result yet.</div>}
        {running && !result && <div className="text-sm text-slate-500">Loading historical candles...</div>}

        {result && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {metric('Accuracy', pct(result.accuracy), result.accuracy >= 0.5 ? 'text-emerald-400' : 'text-rose-400')}
              {metric('Coverage', pct(result.coverage))}
              {metric('Return', bps(result.cumulative_return_bps), cumulativeTone)}
              {metric('Max drawdown', bps(result.max_drawdown_bps), 'text-rose-300')}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="text-slate-400">
                Trades <span className="font-mono text-slate-100">{result.trades}</span>
              </div>
              <div className="text-slate-400">
                Wins <span className="font-mono text-emerald-400">{result.wins}</span>
              </div>
              <div className="text-slate-400">
                Losses <span className="font-mono text-rose-400">{result.losses}</span>
              </div>
              <div className="text-slate-400">
                Avg/trade <span className="font-mono text-slate-100">{bps(result.avg_return_bps, 2)}</span>
              </div>
            </div>

            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-400 text-xs uppercase tracking-wider bg-slate-900/40">
                  <tr>
                    <th className="text-left px-3 py-2">Time</th>
                    <th className="text-left px-3 py-2">Pred</th>
                    <th className="text-left px-3 py-2">Actual</th>
                    <th className="text-right px-3 py-2">Move</th>
                    <th className="text-right px-3 py-2">Return</th>
                    <th className="text-right px-3 py-2">Votes</th>
                    <th className="text-right px-3 py-2">Equity</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(-12).reverse().map((r) => (
                    <tr key={`${r.time}-${r.target_time}`} className="border-t border-slate-800">
                      <td className="px-3 py-2 text-slate-400">{new Date(r.time).toLocaleTimeString()}</td>
                      <td className="px-3 py-2">{badge(r.prediction)}</td>
                      <td className="px-3 py-2">{badge(r.actual)}</td>
                      <td className={`px-3 py-2 text-right font-mono ${r.move_bps >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {bps(r.move_bps, 1)}
                      </td>
                      <td className={`px-3 py-2 text-right font-mono ${r.return_bps >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {bps(r.return_bps, 1)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-300">
                        {r.up_votes}/{r.down_votes}/{r.abstain_votes}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-100">{bps(r.equity_bps, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
