# BTC 5-Min Swarm Predictor

Full-stack web app yang memprediksi arah BTC/USDT (UP/DOWN) untuk 5 menit ke depan
menggunakan **100 AI agent** yang berjalan di **DeepSeek API**, masing-masing dengan
"lensa berpikir" yang berbeda. Hasil swarm ditampilkan di dashboard real-time bersama
data pasar Binance dan referensi pasar prediksi **Polymarket**.

## Arsitektur

```
┌──────────────┐   /api    ┌─────────────────────────────┐   DeepSeek (async, sem=10)
│  React/Vite  │ ────────▶ │   FastAPI backend           │ ─────────────▶  100 agents
│  Tailwind UI │           │  - APScheduler (5m)         │
└──────────────┘           │  - Binance market snapshot  │
                           │  - SQLite (predictions DB)  │
                           │  - Polymarket Gamma API     │
                           └─────────────────────────────┘
```

### Alur kerja
1. Setiap 5 menit (`*/5 second 5`), scheduler mengambil snapshot pasar BTC/USDT
   (harga, 30 candle 1m, 12 candle 5m, RSI/MACD/EMA/Bollinger/ATR/VWAP, depth, FNG).
2. Snapshot dikirim ke 100 agent secara paralel dengan semaphore (default 10 concurrent).
3. Tiap agent membalas JSON `{prediction, confidence, reasoning}`.
4. Hasil diagregasi (UP/DOWN/ABSTAIN, avg confidence, breakdown per kategori) dan disimpan.
5. Setiap menit, scheduler menyelesaikan ronde yang `target_at`-nya sudah lewat dengan
   membandingkan harga aktual ⇒ menulis `actual_outcome` & `is_correct` (live backtest).
6. Backtesting harness dapat dijalankan on-demand terhadap candle historis 1m Binance tanpa
   memanggil DeepSeek, memakai proxy sinyal teknikal deterministik untuk validasi cepat.

## 100 Agent — 10 lensa × 10 spesialis
Lihat [`backend/app/agents.py`](backend/app/agents.py). Kelompok:
- Technical Analysis (RSI, MACD, EMA crossover, SMA, Bollinger, Stochastic, ADX, Ichimoku, VWAP, Volume Profile)
- Price Action & Candlestick (Engulfing, Doji, Pin Bar, Hammer, Three Soldiers, Inside Bar, Breakout, S/R, Trendline, Fibonacci)
- Order Book / Microstructure (Bid-Ask imbalance, Whale walls, Order flow, Spoofing, Spread, Tape, Iceberg, MM bias, Liquidity pockets, Bid stacking)
- On-chain (Inflow, Outflow, Miner flow, SOPR, MVRV, Realized cap, Active addrs, NUPL, Whales, SSR)
- Sentiment (FNG, CT, Reddit, News, Funding, Trends, L/S ratio, Influencer, Telegram, Sentiment delta)
- Derivatives (OI, Funding, Liquidations, Max pain, P/C, Basis, IV, Skew, Gamma, Perp premium)
- Macro (DXY, S&P, Gold, Fed, Yields, Risk regime, Equity beta, Asia open, Friday/weekend, Calendar)
- Statistics (Empirical dist., Markov, Vol regime, Z-score, Hurst, Bayesian, Monte Carlo, Quantile, AC lag-1, Variance ratio)
- ML/Pattern (Pattern match, Lagged returns, Momentum, AC, Regime classifier, Anomaly, RL, Decision tree, Pairs, Time-of-day)
- Meta/Hybrid (Contrarian, Consensus, Devil's advocate, Bayesian aggregator, Confidence weighter, Regime-conditional, TA+sentiment, Multi-TF, Risk-adjusted, Black swan)

## Setup

### Persyaratan
- Python 3.11+
- Node 20+
- Kunci: `DEEPSEEK_API_KEY` (wajib), `BINANCE_API_KEY` (opsional), `POLYMARKET_API_KEY` (opsional)

### 1. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# isi DEEPSEEK_API_KEY dst di .env
uvicorn app.main:app --reload --port 8000
```

Endpoint penting:
- `GET /health`
- `GET /api/agents` — daftar 100 agent
- `GET /api/predictions/latest`
- `GET /api/predictions/history?limit=50`
- `GET /api/predictions/{id}/votes`
- `GET /api/stats`
- `GET /api/backtest?lookback=240&horizon_minutes=5&threshold_bps=0&fee_bps=0`
- `GET /api/market/snapshot`
- `GET /api/polymarket/btc`
- `POST /api/predict/run` — jalankan ronde manual (gunakan untuk first-run sebelum 5 menit pertama)
- `POST /api/predict/settle` — selesaikan ronde yang target_at-nya sudah lewat

Backtesting harness mengembalikan metrik `accuracy`, `coverage`, `cumulative_return_bps`,
`max_drawdown_bps`, `profit_factor`, dan 100 baris hasil terbaru. Parameter:
- `lookback` — jumlah candle 1m yang dievaluasi, 20-900.
- `horizon_minutes` — jarak target harga, default 5 menit.
- `threshold_bps` — zona netral untuk actual outcome; `0` berarti semua pergerakan dihitung.
- `fee_bps` — biaya per trade simulasi dalam basis point.

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Buka http://localhost:5173. Vite mem-proxy `/api/*` ke `http://localhost:8000`.

### 3. Docker (opsional)
```bash
cp backend/.env.example backend/.env   # isi key
docker compose up --build
```
Backend: http://localhost:8000 — Frontend: http://localhost:5173

## Konfigurasi rate limit
- `AGENT_CONCURRENCY=10` di `.env` — atur agar tidak melampaui rate limit DeepSeek.
- Tiap call retry exponential backoff (3 attempts) untuk 429/5xx via `tenacity`.

## Catatan & disclaimer
- Polymarket Gamma API public; kunci hanya untuk rate limit yang lebih tinggi.
- Kontrak spesifik "BTC up/down 5 menit" tidak selalu tersedia di Polymarket. App
  menampilkan market BTC short-term aktif sebagai referensi.
- Ini adalah riset / dashboard edukasi — bukan saran finansial.
