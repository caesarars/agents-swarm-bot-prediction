import { useEffect, useState, useCallback } from 'react'
import { api } from './api.js'
import Countdown from './components/Countdown.jsx'
import VoteSummary from './components/VoteSummary.jsx'
import CategoryBreakdown from './components/CategoryBreakdown.jsx'
import HistoryTable from './components/HistoryTable.jsx'
import MarketPanel from './components/MarketPanel.jsx'
import PolymarketPanel from './components/PolymarketPanel.jsx'
import AgentVotesList from './components/AgentVotesList.jsx'
import BacktestPanel from './components/BacktestPanel.jsx'

export default function App() {
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [snapshot, setSnapshot] = useState(null)
  const [snapshotStatus, setSnapshotStatus] = useState('ok')
  const [polymarket, setPolymarket] = useState([])
  const [stats, setStats] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [backtestRunning, setBacktestRunning] = useState(false)
  const [backtestErr, setBacktestErr] = useState(null)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [l, h, s] = await Promise.all([api.latest(), api.history(30), api.stats()])
      setLatest(l)
      setHistory(h)
      setStats(s)
    } catch (e) {
      setErr(String(e))
    }
  }, [])

  const refreshMarket = useCallback(async () => {
    try {
      const s = await api.snapshot()
      setSnapshot(s)
      setSnapshotStatus('ok')
    } catch {
      setSnapshotStatus('stale')
    }
  }, [])

  const refreshPoly = useCallback(async () => {
    try {
      const m = await api.polymarket()
      setPolymarket(m)
    } catch {
      setPolymarket([])
    }
  }, [])

  const runBacktest = useCallback(async (params = {}) => {
    setBacktestRunning(true)
    setBacktestErr(null)
    try {
      const result = await api.backtest(params)
      setBacktest(result)
    } catch (e) {
      setBacktestErr(String(e))
    } finally {
      setBacktestRunning(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    refreshMarket()
    refreshPoly()
    runBacktest()
    const i1 = setInterval(refresh, 5000)
    const i2 = setInterval(refreshMarket, 6000)
    const i3 = setInterval(refreshPoly, 30000)
    return () => {
      clearInterval(i1)
      clearInterval(i2)
      clearInterval(i3)
    }
  }, [refresh, refreshMarket, refreshPoly, runBacktest])

  const runNow = async () => {
    setRunning(true)
    setErr(null)
    try {
      await api.runNow()
      await refresh()
    } catch (e) {
      setErr(String(e))
    } finally {
      setRunning(false)
    }
  }

  const settleNow = async () => {
    try {
      await api.settleNow()
      await refresh()
    } catch (e) {
      setErr(String(e))
    }
  }

  const accuracyPct = stats?.accuracy != null ? (stats.accuracy * 100).toFixed(1) : '—'
  const polymarketTarget = (polymarket || [])
    .filter((m) => m?.end_date && new Date(m.end_date).getTime() > Date.now() - 15000)
    .sort((a, b) => new Date(a.end_date).getTime() - new Date(b.end_date).getTime())[0]
  const countdownTarget = polymarketTarget?.end_date || latest?.target_at
  const countdownLabel = polymarketTarget ? 'Poly 5m resolves in' : 'Bot round resolves in'

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">BTC 5-Min Swarm Predictor</h1>
            <p className="text-xs text-slate-400">50 DeepSeek primary agents plus 20 Haiku validators.</p>
          </div>
          <div className="flex items-center gap-3">
            <Countdown targetAt={countdownTarget} label={countdownLabel} />
            <button
              onClick={runNow}
              disabled={running}
              className="px-3 py-2 rounded-lg bg-accent text-slate-900 text-sm font-semibold disabled:opacity-50"
            >
              {running ? 'Running…' : 'Run round now'}
            </button>
            <button
              onClick={settleNow}
              className="px-3 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm font-medium"
            >
              Settle due
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {err && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/40 px-4 py-2 text-rose-300 text-sm">
            {err}
          </div>
        )}

        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <VoteSummary prediction={latest} />
            <CategoryBreakdown breakdown={latest?.category_breakdown} />
          </div>
          <div className="space-y-6">
            <MarketPanel snapshot={snapshot} status={snapshotStatus} />
            <div className="rounded-xl bg-card p-6 border border-slate-800">
              <div className="text-xs uppercase tracking-wider text-slate-400">Backtest accuracy</div>
              <div className="text-3xl font-bold font-mono mt-1">{accuracyPct}{accuracyPct !== '—' && '%'}</div>
              <div className="text-xs text-slate-500 mt-1">
                {stats?.correct_predictions ?? 0}/{stats?.settled_predictions ?? 0} settled rounds
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <PolymarketPanel markets={polymarket} />
          <AgentVotesList predictionId={latest?.id} />
        </section>

        <section>
          <BacktestPanel result={backtest} running={backtestRunning} error={backtestErr} onRun={runBacktest} />
        </section>

        <section>
          <HistoryTable rows={history} />
        </section>

        <footer className="text-center text-xs text-slate-600 pt-4 pb-10">
          BTC data via Binance. Sentiment via Alternative.me. Reference odds via Polymarket Gamma API.
          This is research / educational tooling, not financial advice.
        </footer>
      </main>
    </div>
  )
}
