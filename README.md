# TradeWatch

A standalone Indian equity market trading signal scanner with price alerts and backtesting. Scans Nifty 500 stocks every market close for momentum signals, lets you set price alerts, and notifies you on Telegram when they trigger.

---

## Features

- **Daily Scanner** — scans all active Nifty 500 stocks at 15:45 IST for stocks that have returned ≥10% over the last 4 trading days (both configurable)
- **Signal Browser** — browse signals from any past scan date with a date picker
- **Price Alerts** — set a target entry price on any signal; get notified when LTP drops to or below your price
- **Telegram Notifications** — instant alert on trigger; test message from Settings to verify setup
- **Backtesting** — replay the scanner on any stock over any date range to see every qualifying day
- **Local Candle Cache** — OHLC data fetched from Dhan API is cached in SQLite; repeat scans and backtests are instant
- **Token Auto-Renewal** — Dhan access token renewed automatically at 09:00 IST daily
- **Encrypted Storage** — Dhan and Telegram tokens stored encrypted at rest (Fernet AES-128)
- **Fully Configurable UI** — scan time, threshold %, trading days, alert interval — all editable from Settings without restart

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Your Machine                      │
│                                                      │
│   ┌──────────────┐   HTTP    ┌────────────────────┐  │
│   │    React     │◄─────────►│   FastAPI Backend  │  │
│   │  Frontend    │           │   localhost:8000   │  │
│   │  :5173       │           │                    │  │
│   └──────────────┘           │  ┌──────────────┐  │  │
│                              │  │  API Routers │  │  │
│                              │  │  /signals    │  │  │
│                              │  │  /alerts     │  │  │
│                              │  │  /backtest   │  │  │
│                              │  │  /config     │  │  │
│                              │  └──────┬───────┘  │  │
│                              │         │          │  │
│                              │  ┌──────▼───────┐  │  │
│                              │  │   Services   │  │  │
│                              │  │  Scanner     │  │  │
│                              │  │  Alerts      │  │  │
│                              │  │  Backtest    │  │  │
│                              │  │  Dhan        │  │  │
│                              │  │  Telegram    │  │  │
│                              │  └──┬───────┬───┘  │  │
│                              │     │       │      │  │
│                              │  ┌──▼──┐ ┌─▼────┐  │  │
│                              │  │APSch│ │SQLite│  │  │
│                              │  │uler │ │  DB  │  │  │
│                              │  └──┬──┘ └──────┘  │  │
│                              └─────┼──────────────┘  │
└─────────────────────────────────── ┼ ────────────────┘
                                     │
              ┌──────────────────────┼──────────────┐
              ▼                      ▼               ▼
     ┌──────────────┐    ┌───────────────────┐  ┌──────────┐
     │  Dhan API    │    │  Dhan API         │  │ Telegram │
     │  Historical  │    │  LTP (live price) │  │ Bot API  │
     │  OHLC data   │    │  every 30 mins    │  │          │
     └──────────────┘    └───────────────────┘  └──────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic |
| Database | SQLite |
| Scheduler | APScheduler 3.x (embedded in FastAPI) |
| Stock Data | Dhan API (`dhanhq` SDK) |
| Notifications | `python-telegram-bot` |
| Encryption | `cryptography` (Fernet) |
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui |
| Charts | Recharts |
| API Client | Axios + React Query |

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Dhan account | — | For API access token and client ID |
| Telegram bot | — | Bot token + chat ID (optional, for notifications) |

### Getting Dhan API credentials

1. Log in to [Dhan](https://dhan.co) and go to **My Profile → Apps**
2. Create an app to get your **Client ID** and **Access Token**
3. Access tokens expire every 24 hours — TradeWatch auto-renews them daily at 09:00 IST

### Setting up a Telegram bot (optional)

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the **bot token**
2. Add the bot to a group or channel → get the **chat ID** via `https://api.telegram.org/bot<TOKEN>/getUpdates`

---

## Local Setup

### 1. Clone the repository

```bash
git clone git@github.com:amrakshay/tradewatch.git
cd tradewatch
```

### 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize the database
alembic upgrade head

# Seed default config row
python scripts/seed_db.py
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

### 4. Environment (optional)

The app stores all credentials in the database via the Settings UI — no `.env` file is required for normal use. If you prefer environment-based config:

```bash
cd backend
cp .env.example .env
# Fill in DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

---

## Running

### Start everything

```bash
# From the project root
./start.sh
```

This starts the FastAPI backend on port 8000 and the Vite dev server on port 5173. Press `Ctrl+C` to stop both.

### Or start manually

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Web UI |
| http://localhost:8000/docs | API docs (Swagger UI) |
| http://localhost:8000/health | Health check |

---

## First-Time Configuration

1. Open http://localhost:5173 and go to **Settings**
2. Under **Dhan API** — enter your Client ID and Access Token, then click **Test Connection**
3. Under **Telegram** (optional) — enter bot token and chat ID, then click **Send Test Message**
4. Under **Stock Universe** — click **Sync Nifty 500** to download ~500 stocks (takes ~30 seconds)
5. Done — the scanner will run automatically at 15:45 IST on trading days

---

## Development Guide

### Project layout

```
backend/app/
├── main.py          # FastAPI app, lifespan (scheduler start/stop)
├── database.py      # SQLAlchemy engine, SessionLocal, Base, get_db()
├── models/          # One file per table (config, stock, signal, alert, candle)
├── schemas/         # Pydantic schemas for each domain
├── routers/         # Route handlers (thin — delegate to services)
└── services/        # All business logic lives here
    ├── encryption.py       # Fernet encrypt/decrypt/mask
    ├── config_service.py   # Read/write app_config; dispatches side effects
    ├── token_service.py    # Dhan token validity check + renewal
    ├── dhan_service.py     # Dhan API wrapper + cache-first get_daily_ohlc()
    ├── candle_cache.py     # SQLite OHLC cache: store, get, gap detection
    ├── scanner_service.py  # Daily scan logic + signal persistence
    ├── alert_service.py    # Alert CRUD + check_alerts() monitor
    ├── telegram_service.py # Telegram notifications
    └── backtest_service.py # Backtest engine
```

### Adding a new migration

After editing a SQLAlchemy model in `backend/app/models/`:

```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "describe_your_change"
# Review the generated file in alembic/versions/
alembic upgrade head
```

### Key conventions

**Timestamps** — always use IST via Python, never SQLite functions:
```python
from zoneinfo import ZoneInfo
from datetime import datetime
IST = ZoneInfo("Asia/Kolkata")

created_at = datetime.now(IST).isoformat()  # ✅
# NOT: func.now() or datetime.utcnow()      # ❌
```

**Candle data** — always use the cache-first method:
```python
candles = await dhan_service.get_daily_ohlc(security_id, from_date, to_date, db=db)
# NOT: dhan_service.get_daily_ohlc_raw(...)
```

**Telegram messages** — always HTML parse mode with escaped user content:
```python
import html
text = f"Stock: <b>{html.escape(symbol)}</b>"
bot.send_message(chat_id=..., text=text, parse_mode="HTML")
```

**Sensitive config** — read via `get_decrypted_config(db)`, never access `AppConfig.dhan_access_token` directly (it's a ciphertext).

### Useful commands

```bash
# Check which migration is applied
alembic current

# See migration history
alembic history

# Inspect the database directly
sqlite3 backend/tradewatch.db ".tables"
sqlite3 backend/tradewatch.db "SELECT scan_date, COUNT(*) FROM scan_signals GROUP BY scan_date ORDER BY scan_date DESC LIMIT 10;"

# Trigger a manual scan (no need to wait for 15:45)
curl -X POST http://localhost:8000/api/scanner/run

# Check scheduler jobs and next run times
curl http://localhost:8000/api/scheduler/status
```

### Running the API interactively

With the backend running, open http://localhost:8000/docs for the full Swagger UI — every endpoint is documented and testable from the browser.

---

## Documentation

| Document | Description |
|----------|-------------|
| `ARCHITECTURE.md` | Full system design, component details, API spec, scheduler design |
| `docs/plan/PLAN.md` | Implementation phases, task index, dependency graph |
| `docs/plan/tasks/` | T01–T22 detailed task specs with step-by-step implementation |
| `docs/adr/` | ADR-001–ADR-013 architecture decision records |
