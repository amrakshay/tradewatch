# TradeWatch — Agent Context

Indian equity market trading signal scanner. Scans Nifty 500 stocks daily at 15:45 IST for stocks with >10% return in the last 4 trading days (configurable), stores signals, lets users set price alerts, monitors them every 30 mins, sends Telegram notifications on trigger, and supports backtesting.

**Full architecture:** `ARCHITECTURE.md`
**Implementation plan:** `docs/plan/PLAN.md`
**Individual task files:** `docs/plan/tasks/T01-*.md … T22-*.md`
**Architecture decisions:** `docs/adr/ADR-001-*.md … ADR-013-*.md`

---

## Project Structure

```
tradewatch/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── database.py          # SQLAlchemy engine + session + Base
│   │   ├── models/              # SQLAlchemy ORM models (6 tables)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # FastAPI route handlers
│   │   ├── services/            # Business logic (scanner, alerts, dhan, etc.)
│   │   └── scheduler/           # APScheduler job definitions
│   ├── alembic/                 # Database migrations
│   │   └── versions/            # Migration files (commit these)
│   ├── alembic.ini              # Alembic config (DB URL: sqlite:///./tradewatch.db)
│   ├── scripts/seed_db.py       # Seeds default app_config row (run after migrations)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    # React 18 + Vite + Tailwind + shadcn/ui
│   └── src/
│       ├── pages/               # Dashboard, Signals, Alerts, Backtest, Settings
│       ├── components/          # layout/, signals/, alerts/, backtest/
│       ├── api/                 # Axios API wrappers per domain
│       └── hooks/
├── docs/
│   ├── plan/tasks/              # T01–T22 detailed task specs
│   └── adr/                     # ADR-001–ADR-013 decision records
├── start.sh                     # Starts backend + frontend together
└── ARCHITECTURE.md
```

---

## Running the Project

```bash
# Start everything
./start.sh

# Or manually:
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

Backend: http://localhost:8000 | Frontend: http://localhost:5173 | API docs: http://localhost:8000/docs

---

## Database

- **Engine:** SQLite (`backend/tradewatch.db`) — auto-created by Alembic
- **Migrations:** Alembic (never use `Base.metadata.create_all()` in production)
- **6 tables:** `app_config`, `stocks`, `scan_signals`, `alerts`, `alert_history`, `candle_cache`

```bash
cd backend && source .venv/bin/activate

# Initialize / upgrade schema
alembic upgrade head

# Seed default config row (run once after first migration)
python scripts/seed_db.py

# Add a new migration after editing a model
alembic revision --autogenerate -m "describe_change"
alembic upgrade head

# Check status
alembic current
```

---

## Key Conventions

**Timestamps — always IST, always Python:**
```python
from zoneinfo import ZoneInfo
from datetime import datetime
IST = ZoneInfo("Asia/Kolkata")
datetime.now(IST).isoformat()   # ✅
# Never: func.now(), datetime.utcnow(), SQLite datetime('now')
```

**Encryption — Fernet for sensitive fields:**
- `dhan_access_token` and `telegram_bot_token` are stored encrypted via `EncryptionService`
- Key file: `backend/.secret_key` (auto-generated; never commit; already in .gitignore)
- Key path resolved as: `Path(__file__).resolve().parents[2] / ".secret_key"`

**Alert trigger:** `LTP <= alert_price` (pullback to target entry)

**Scan time default:** 15:45 IST (15 min after close to let Dhan finalize the candle)

**Candle cache:** All OHLC calls go through `DhanService.get_daily_ohlc()` (cache-first), never `get_daily_ohlc_raw()` directly. Today's candle is not cached before 15:30 IST.

**Telegram:** HTML parse mode + `html.escape()` on all user strings. Never use Markdown parse mode.

**Scheduler:** 4 jobs — `token_renew` (09:00), `daily_scan` (15:45), `alert_monitor` (interval), `alert_monitor_close` (15:30 cron, `bypass_window_guard=True`). Reschedule via `scheduler.reschedule_job()` when config changes — no restart needed.

**Backtest buffer:** Always prepend 14 calendar days before `from_date` when fetching candles.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic |
| Scheduler | APScheduler 3.x (AsyncIOScheduler, embedded in FastAPI) |
| Database | SQLite (`tradewatch.db`) |
| Stock data | `dhanhq` SDK (Dhan API) |
| Notifications | `python-telegram-bot` (async) |
| Encryption | `cryptography` (Fernet) |
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui, Recharts |
| API client | Axios + React Query |

---

## Task Status

Completed: **T01** (project structure), **T02** (DB models + Alembic migrations)

Remaining tasks are in `docs/plan/tasks/`. Each file has: goal, files to create, step-by-step implementation, and a "Done When" checklist.

**To work on a task:**
```
Read docs/plan/tasks/T<NN>-<name>.md and implement it end to end.
Use ARCHITECTURE.md for any context not covered in the task file.
Verify every item in the "Done When" section before committing.
Commit when complete.
```

**Task dependency order (see PLAN.md for full graph):**
- Phase 0 (done): T01, T02, T03, T04
- Phase 1: T05, T06, T07, T08, T09
- Phase 2: T10, T11, T14, T15, T16
- Phase 3: T12, T13, T17, T18, T19, T20
- Phase 4: T21, T22

---

## Do Not

- Do not use `Base.metadata.create_all()` anywhere except tests
- Do not write timestamps using `datetime.utcnow()` or SQLite `datetime('now')`
- Do not send Telegram messages with `parse_mode="Markdown"` or `"MarkdownV2"`
- Do not call `get_daily_ohlc_raw()` directly from services — always use `get_daily_ohlc()`
- Do not commit `tradewatch.db`, `.secret_key`, or `.env`
