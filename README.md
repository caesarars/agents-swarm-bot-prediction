# BTC 15-Min Swarm Predictor

Full-stack web app yang memprediksi arah BTC/USDT (UP/DOWN) untuk 15 menit ke depan
menggunakan **60 grounded agents**: 30 DeepSeek, 20 Claude Haiku, dan 10 Gemini.
Hasil swarm ditampilkan di dashboard real-time bersama data pasar Binance dan referensi
pasar prediksi **Polymarket**.

## Arsitektur

```
┌──────────────┐   /api    ┌─────────────────────────────┐   DeepSeek + Claude + Gemini
│  React/Vite  │ ────────▶ │   FastAPI backend           │ ─────────────▶  60 grounded agents
│  Tailwind UI │           │  - APScheduler (15m)        │
└──────────────┘           │  - Binance spot + futures   │
                           │  - SQLite (predictions DB)  │
                           │  - Polymarket Gamma API     │
                           └─────────────────────────────┘
```

### Alur kerja
1. Setiap 15 menit (`minute=*/15, second=30`), scheduler mengambil snapshot pasar BTC/USDT
   (harga, 30 candle 15m, 16 candle 5m, RSI/MACD/EMA/Bollinger/ATR/VWAP, depth,
   Binance Futures premium/funding/open interest, FNG).
2. Snapshot dikirim ke 60 agent secara paralel dengan semaphore (default 10 concurrent).
3. Tiap agent membalas JSON `{prediction, confidence, reasoning}`.
4. Hasil diagregasi (UP/DOWN/ABSTAIN, avg confidence, breakdown per kategori) dan disimpan.
5. Setiap menit, scheduler menyelesaikan ronde yang `target_at`-nya sudah lewat dengan
   membandingkan harga aktual ⇒ menulis `actual_outcome` & `is_correct` (live backtest).
6. Backtesting harness dapat dijalankan on-demand terhadap candle historis 15m Binance tanpa
   memanggil DeepSeek, memakai proxy sinyal teknikal deterministik untuk validasi cepat.

## Agent Swarm
Lihat [`backend/app/agents.py`](backend/app/agents.py). Roster saat ini:
- 6 lensa yang sesuai dengan snapshot: Technical Analysis, Price Action, Order Book, Futures, Statistics, Sentiment.
- 60 agent total: 30 DeepSeek, 20 Claude Haiku, 10 Gemini.
- 10 specialist per lensa, termasuk Futures specialist yang memakai Binance Futures public data.
- Aggregator memakai `primary_confirm`: DeepSeek tetap primary, Claude/Gemini menjadi validator berbobot.

Agent on-chain, macro, options, liquidations, dan news dihapus dari swarm karena snapshot belum menyediakan
SOPR, liquidation levels, DXY, SPX, news feed, atau feed sejenis. Ini
mengurangi noise dari agent yang sebelumnya berisiko mengarang data.

## Setup

### Persyaratan
- Python 3.11+
- Node 20+
- Kunci LLM: `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`
- Kunci data: `BINANCE_API_KEY` (opsional), `POLYMARKET_API_KEY` (opsional)

### 1. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# isi DEEPSEEK_API_KEY dan ANTHROPIC_API_KEY dst di .env
uvicorn app.main:app --reload --port 8000
```

Endpoint penting:
- `GET /health`
- `GET /api/agents` — daftar 60 agent
- `GET /api/predictions/latest`
- `GET /api/predictions/history?limit=50`
- `GET /api/predictions/{id}/votes`
- `GET /api/stats`
- `GET /api/learning/performance`
- `GET /api/backtest?lookback=240&interval=15m&horizon_minutes=15&threshold_bps=0&fee_bps=0`
- `GET /api/market/snapshot`
- `GET /api/polymarket/btc`
- `POST /api/predict/run` — jalankan ronde manual (gunakan untuk first-run sebelum 15 menit pertama)
- `POST /api/predict/settle` — selesaikan ronde yang target_at-nya sudah lewat

Backtesting harness mengembalikan metrik `accuracy`, `coverage`, `cumulative_return_bps`,
`max_drawdown_bps`, `profit_factor`, dan 100 baris hasil terbaru. Parameter:
- `lookback` — jumlah candle 15m yang dievaluasi, 20-900.
- `horizon_minutes` — jarak target harga, default 15 menit.
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

## Konfigurasi agregasi swarm
- `SWARM_AGGREGATION_MODE=primary_confirm` — default: DeepSeek primary, Haiku validator.
- `SWARM_DEEPSEEK_WEIGHT=1.0` — bobot provider DeepSeek.
- `SWARM_ANTHROPIC_WEIGHT=0.35` — bobot Haiku dibuat kecil agar tidak mendominasi primary swarm.

## Learning dari hasil settled
- `LEARNING_ENABLED=true` — aktifkan bobot adaptif dari ronde yang sudah settled.
- `LEARNING_LOOKBACK=200` — jumlah ronde settled terakhir yang dipakai untuk menghitung performa.
- `LEARNING_MIN_AGENT_SAMPLES=8` — minimal sampel sebelum bobot agent dipakai.
- `LEARNING_MIN_WEIGHT=0.35`, `LEARNING_MAX_WEIGHT=1.8` — batas bobot agar learning tidak overfit.
- Bobot dihitung dari akurasi historis per agent, category, dan provider, lalu disimpan di `market_snapshot.aggregation.learning`.
- Dashboard menampilkan top/bottom weighted agents dan bobot kategori dari `GET /api/learning/performance`.

## Catatan & disclaimer
- Polymarket Gamma API public; kunci hanya untuk rate limit yang lebih tinggi.
- Kontrak spesifik "BTC up/down 15 menit" tidak selalu tersedia di Polymarket. App
  menampilkan market BTC short-term aktif sebagai referensi.
- Ini adalah riset / dashboard edukasi — bukan saran finansial.
