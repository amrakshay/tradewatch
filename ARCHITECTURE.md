# PullbackScanner — System Architecture & Implementation Plan

> Indian equity market pullback opportunity scanner with alert system, Telegram notifications, and backtesting engine.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Diagram](#3-architecture-diagram)
4. [Component Design](#4-component-design)
5. [Database Schema](#5-database-schema)
6. [API Specification](#6-api-specification)
7. [Dhan API Integration](#7-dhan-api-integration)
8. [Dhan Token Lifecycle](#8-dhan-token-lifecycle)
9. [Scheduler Design](#9-scheduler-design)
10. [Frontend Pages](#10-frontend-pages)
11. [Backtesting Engine](#11-backtesting-engine)
12. [Telegram Notification](#12-telegram-notification)
13. [Project Structure](#13-project-structure)
14. [Implementation Plan](#14-implementation-plan)
15. [Architecture Decisions](#15-architecture-decisions)
16. [Confirmed Decisions & Assumptions](#16-confirmed-decisions--assumptions)

---

## 1. System Overview

PullbackScanner is a standalone desktop/server application that:

- **Scans** Nifty 500 (or any configured stock list) every market close (~3:30 PM IST) for stocks that have risen more than a configurable % (default 10%) over a configurable number of days (default 4)
- **Stores** qualifying stocks as dated "signals" in a local SQLite database
- **Lets you browse** any past date's signals and manually set a price alert with an expiry window
- **Monitors** active alert prices every 30 minutes during market hours and **sends a Telegram notification** when an alert triggers
- **Backtests** any stock over any date range to see which days it would have appeared in the scanner

### Key Design Goals

- **Standalone** — single machine, no cloud infrastructure required
- **Configurable from UI** — no config file editing
- **Simple & maintainable** — minimal dependencies, clear separation of concerns
- **Resilient** — graceful handling of Dhan API failures, rate limits, market holidays
- **Secure** — sensitive credentials (tokens, API keys) stored encrypted at rest
- **API-efficient** — candle data cached locally in SQLite; Dhan API only called for missing date ranges

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend API | Python 3.11 + FastAPI | Async support, excellent typing, auto-docs |
| Database | SQLite (via SQLAlchemy) | Zero-ops, sufficient for single-user |
| ORM | SQLAlchemy 2.x (sync) | Mature, good SQLite support |
| Scheduler | APScheduler 3.x | Embeds in FastAPI process, cron + interval |
| Stock Data | Dhan SDK (`dhanhq`) | Official Python client |
| Telegram | `python-telegram-bot` (async) | Official library |
| Frontend | React 18 + Vite | Fast dev experience |
| UI Styling | Tailwind CSS + shadcn/ui | Clean light theme, no custom CSS needed |
| HTTP Client (FE) | Axios + React Query | Caching, loading states |
| Charts (FE) | Recharts | Lightweight, composable |
| Encryption | Python `cryptography` (Fernet) | Symmetric AES-128 encryption for stored credentials |

---

## 3. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User's Machine                          │
│                                                             │
│  ┌─────────────────┐        ┌──────────────────────────┐   │
│  │  React Frontend │◄──────►│   FastAPI Backend        │   │
│  │  (Vite dev /    │  HTTP  │   localhost:8000         │   │
│  │   static build) │        │                          │   │
│  │  localhost:5173 │        │  ┌────────────────────┐  │   │
│  └─────────────────┘        │  │  REST API Routers  │  │   │
│                             │  │  /api/config       │  │   │
│                             │  │  /api/stocks       │  │   │
│                             │  │  /api/signals      │  │   │
│                             │  │  /api/alerts       │  │   │
│                             │  │  /api/backtest     │  │   │
│                             │  └────────┬───────────┘  │   │
│                             │           │              │   │
│                             │  ┌────────▼───────────┐  │   │
│                             │  │    Service Layer   │  │   │
│                             │  │  ScannerService    │  │   │
│                             │  │  AlertService      │  │   │
│                             │  │  BacktestService   │  │   │
│                             │  │  DhanService       │  │   │
│                             │  │  TelegramService   │  │   │
│                             │  └──┬─────────────┬───┘  │   │
│                             │     │             │      │   │
│                             │  ┌──▼──┐    ┌────▼────┐  │   │
│                             │  │APSch│    │ SQLite  │  │   │
│                             │  │uler │    │  DB     │  │   │
│                             │  └──┬──┘    └─────────┘  │   │
│                             └─────┼────────────────────┘   │
│                                   │                        │
└───────────────────────────────────┼────────────────────────┘
                                    │
              ┌─────────────────────┼──────────────────┐
              │                     │                  │
              ▼                     ▼                  ▼
     ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐
     │  Dhan API       │  │  Dhan API        │  │  Telegram    │
     │  (Historical)   │  │  (LTP / Quote)   │  │  Bot API     │
     │  3:30 PM scan   │  │  Every 30 mins   │  │  Alerts      │
     └─────────────────┘  └──────────────────┘  └──────────────┘
```

---

## 4. Component Design

### 4.1 DhanService

Thin wrapper around the `dhanhq` Python SDK. All Dhan API calls go through this service.

**Responsibilities:**
- Initialize SDK with credentials from config (credentials decrypted by ConfigService before being passed in)
- `get_daily_ohlc(security_id, from_date, to_date)` → daily candle data, **cache-first via CandleCacheService**
- `get_ltp_batch(securities: dict)` → LTP for up to 1000 instruments in one call (never cached — always live)
- `get_instrument_list()` → download and parse Dhan's master CSV
- Handle rate limiting with retry + exponential backoff
- Reload credentials when config changes

**Rate Limit Awareness (from Dhan docs):**
- Data APIs (Historical): 5 req/sec, 100,000/day
- Quote APIs (LTP): 1 req/sec, unlimited/day
- Scanning 500 stocks historically takes ~100 seconds (500 calls at 5/sec) — acceptable for a background job
- LTP monitoring batches all active-alert stocks into **one call** (up to 1000 in single request) — very efficient

### 4.2 ScannerService

**Responsibilities:**
- Load active stock universe from DB
- For each stock, fetch last N+1 days of daily candle data via DhanService
- Calculate: `return_pct = (close_today - close_N_days_ago) / close_N_days_ago * 100`
- Filter stocks where `return_pct >= threshold`
- Persist qualifying stocks to `scan_signals` table with today's date
- Return scan summary

**Scan Logic (example: 10% in 4 days):**
```
close[today] - close[4 trading days ago]
─────────────────────────────────────── × 100 ≥ 10%
         close[4 trading days ago]
```

Note: "4 days" means 4 trading days (market days), not calendar days. Since we use Dhan's daily candle data, which only contains trading days, `close[-4]` is automatically the 4th prior trading day.

### 4.3 AlertService

**Responsibilities:**
- CRUD for alerts
- `check_alerts()` — called every 30 mins by scheduler:
  1. Load all `active` alerts within their valid window
  2. Batch all their security IDs into one LTP call to Dhan
  3. For each alert where `LTP <= alert_price`:
     - Update alert status to `triggered`
     - Record `triggered_at` and `triggered_price`
     - Append to `alert_history`
     - Send Telegram notification via TelegramService
  4. For each alert past its `expires_at`:
     - Update status to `expired`

**Alert States:**
```
created → active → triggered
                → expired
                → deleted (manual)
```

### 4.4 BacktestService

**Responsibilities:**
- Accept: `symbol`, `security_id`, `from_date`, `to_date`, `pct_threshold`, `num_days`
- Fetch full daily OHLC for the date range (prefetch `from_date - 14 calendar days` as lookback buffer)
- For each trading day in range, apply scanner logic
- Return list of `{date, close_price, start_price, return_pct}` for days that qualified

**Algorithm:**
```python
candles = fetch_daily_ohlc(security_id, from_date - N_days_buffer, to_date)
results = []
for i in range(num_days, len(candles)):
    today_close = candles[i].close
    start_close = candles[i - num_days].close
    ret = (today_close - start_close) / start_close * 100
    if ret >= pct_threshold:
        results.append({date, today_close, start_close, ret})
return results
```

### 4.5 TelegramService

**Responsibilities:**
- Send message to configured chat_id via bot token
- `send_alert_triggered(symbol, alert_price, triggered_price, signal_date)`
- `send_test_message()` — for config validation

**Message format example:**
```
🔔 Alert Triggered: RELIANCE
Signal Date: 2024-01-15
Alert Price: ₹2,450.00
Current Price: ₹2,448.50
```

### 4.6 ConfigService

- Reads/writes a single row in the `app_config` table
- Exposes typed config object to all other services
- Decrypts sensitive fields before returning them to other services; encrypts on write
- On every `PUT /config`, diffs the old vs new values and fires the appropriate side effects:

| Changed field | Side effect |
|---|---|
| `scan_time` | `scheduler.reschedule_job("daily_scan", trigger=CronTrigger(...))` |
| `alert_check_interval_mins` | `scheduler.reschedule_job("alert_monitor", trigger=IntervalTrigger(...))` |
| `alert_check_start` / `alert_check_end` | Update in-memory bounds used by `check_alerts()` guard |
| `dhan_client_id` / `dhan_access_token` | Re-initialize DhanService SDK instance |
| `telegram_bot_token` / `telegram_chat_id` | Re-initialize TelegramService bot instance |

This means the scheduler and service layer always reflect the live DB config without requiring a restart. The scheduler instance is injected into ConfigService at startup (or accessed via a module-level singleton).

### 4.7 EncryptionService

Handles encryption/decryption of sensitive fields stored in `app_config`.

**Approach:** Fernet symmetric encryption (`cryptography` library — AES-128-CBC + HMAC-SHA256).

**Key storage:**
- A random 32-byte encryption key is generated on first run
- Stored in a local file: `backend/.secret_key` (should be in `.gitignore`)
- Never stored in the database
- If the key file is deleted, stored credentials become unreadable and must be re-entered

**Which fields are encrypted:**
- `dhan_access_token`
- `telegram_bot_token`

**Which fields are NOT encrypted:**
- `dhan_client_id` — not a secret by itself, just an identifier
- `telegram_chat_id` — not a secret
- All scan/scheduler settings — not sensitive

**API behavior:**
- `GET /config` returns tokens **masked** (e.g., `"ey...abc"` — first 2 and last 3 chars only) so the UI can show "token is set" without exposing the full value
- `PUT /config` accepts the full token value, encrypts it, stores it
- If the PUT body contains a masked value (user didn't change it), the existing encrypted value is preserved

**Implementation sketch:**
```python
from cryptography.fernet import Fernet
from pathlib import Path

# Resolve key path relative to this source file, not cwd.
# encryption.py lives at backend/app/services/encryption.py
# → go up 3 levels to reach backend/, then .secret_key
_DEFAULT_KEY_PATH = Path(__file__).resolve().parents[2] / ".secret_key"

class EncryptionService:
    def __init__(self, key_path: Path = _DEFAULT_KEY_PATH):
        key_path = Path(key_path)
        if not key_path.exists():
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(Fernet.generate_key())
        self._fernet = Fernet(key_path.read_bytes())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()

    def mask(self, value: str) -> str:
        if len(value) <= 6:
            return "***"
        return value[:2] + "..." + value[-3:]
```

### 4.8 CandleCacheService

Local SQLite cache for daily OHLC data fetched from Dhan. Eliminates redundant API calls for the same stock and date range.

**Responsibilities:**
- `get_cached_candles(security_id, from_date, to_date)` → returns available rows from cache
- `find_missing_ranges(security_id, from_date, to_date, cached_dates)` → computes date gaps not in cache
- `store_candles(security_id, candles[])` → upserts rows into `candle_cache`
- Used by `DhanService` as a transparent cache layer

**Cache-first fetch flow:**
```
Request: candles for RELIANCE from 2023-01-01 to 2024-01-01

1. Query candle_cache for security_id=2885, date in range
2. Identify which trading dates are missing
   → If all dates present: return from cache, 0 API calls
   → If partial: fetch only missing ranges from Dhan, store, merge with cached
   → If none: fetch full range from Dhan, store, return

3. Return merged sorted candle list
```

**Gap detection logic:**
```python
def find_missing_ranges(security_id, from_date, to_date, cached_dates: set):
    # Build expected trading-day set using a simple calendar
    # (weekdays only — Dhan simply returns no data for holidays,
    #  so we treat "no data returned" as "no trading day")
    # Compare expected vs cached_dates → return contiguous missing ranges
    # Return as list of (range_from, range_to) tuples for batched API calls
```

**Important cache behaviors:**
- Cache is never invalidated for past dates — historical OHLC doesn't change
- Current day's candle (today) is NOT cached until after market close (3:30 PM), to avoid caching a mid-session partial candle during backtest runs
- Cache is transparent: `ScannerService` and `BacktestService` always call `DhanService.get_daily_ohlc()`, which internally uses `CandleCacheService`

---

## 5. Database Schema

Using SQLite with SQLAlchemy. One database file: `pullback.db`

**Timezone convention — IST everywhere:**
All timestamps stored in the database are **IST (Asia/Kolkata, UTC+5:30)**. SQLite's built-in `datetime('now')` returns UTC, which would cause off-by-one-day mismatches for operations after 18:30 IST (midnight UTC). Instead:
- All `DEFAULT (datetime('now'))` columns are populated by SQLAlchemy, not by SQLite defaults, using `datetime.now(IST)` in Python before writing.
- `scan_date`, `signal_date`, `expires_at`, `triggered_at`, `created_at`, `timestamp` all carry IST values.
- SQLite stores them as ISO 8601 strings (`YYYY-MM-DD HH:MM:SS`) with no timezone suffix — the IST convention is enforced at the application layer.

### 5.1 `app_config`

Singleton row — only one row ever exists.

```sql
CREATE TABLE app_config (
    id                  INTEGER PRIMARY KEY DEFAULT 1,

    -- Scanner settings
    scan_time           TEXT    NOT NULL DEFAULT '15:45',  -- HH:MM IST; default 15:45 to allow candle finalization after 15:30 close
    scan_percentage     REAL    NOT NULL DEFAULT 10.0,
    scan_days           INTEGER NOT NULL DEFAULT 4,

    -- Alert monitor settings
    alert_check_interval_mins INTEGER NOT NULL DEFAULT 30,
    alert_check_start   TEXT    NOT NULL DEFAULT '09:15',
    alert_check_end     TEXT    NOT NULL DEFAULT '15:30',

    -- Dhan credentials
    dhan_client_id      TEXT    NOT NULL DEFAULT '',
    dhan_access_token   TEXT    NOT NULL DEFAULT '',  -- stored Fernet-encrypted
    token_expires_at    TEXT,                          -- IST ISO timestamp from Dhan expiryTime
    token_status        TEXT    NOT NULL DEFAULT 'unknown',
                                                      -- unknown | active | expiring_soon | expired

    -- Telegram
    telegram_bot_token  TEXT    NOT NULL DEFAULT '',  -- stored Fernet-encrypted
    telegram_chat_id    TEXT    NOT NULL DEFAULT '',

    updated_at          TEXT    NOT NULL  -- set in Python: datetime.now(IST).isoformat()
);
```

### 5.2 `stocks`

Master list of tracked stocks. Pre-loaded with Nifty 500 but fully editable.

```sql
CREATE TABLE stocks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT    NOT NULL,          -- e.g. "RELIANCE"
    name             TEXT    NOT NULL,          -- e.g. "Reliance Industries"
    security_id      TEXT    NOT NULL UNIQUE,   -- Dhan internal ID e.g. "2885"
    exchange_segment TEXT    NOT NULL DEFAULT 'NSE_EQ',
    universe_tag     TEXT    NOT NULL DEFAULT 'NIFTY500', -- label, purely informational
    is_active        INTEGER NOT NULL DEFAULT 1,   -- 0=disabled, 1=enabled
    added_at         TEXT    NOT NULL  -- set in Python: datetime.now(IST).isoformat()
);
```

### 5.3 `scan_signals`

One row per stock per scan run where the stock qualified.

```sql
CREATE TABLE scan_signals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date        TEXT    NOT NULL,  -- YYYY-MM-DD (the date of the scan)
    symbol           TEXT    NOT NULL,
    security_id      TEXT    NOT NULL,
    close_price      REAL    NOT NULL,  -- today's close
    start_price      REAL    NOT NULL,  -- close N trading days ago
    return_pct       REAL    NOT NULL,  -- (close - start) / start * 100
    scan_days        INTEGER NOT NULL,  -- N used at scan time
    scan_threshold   REAL    NOT NULL,  -- threshold used at scan time
    created_at       TEXT    NOT NULL,  -- set in Python: datetime.now(IST).isoformat()

    UNIQUE(scan_date, security_id)      -- prevent duplicate signals
);

CREATE INDEX idx_signals_date ON scan_signals(scan_date);
CREATE INDEX idx_signals_symbol ON scan_signals(symbol);
```

### 5.4 `alerts`

```sql
CREATE TABLE alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT    NOT NULL,
    security_id      TEXT    NOT NULL,
    signal_date      TEXT    NOT NULL,     -- which scan date prompted this alert
    alert_price      REAL    NOT NULL,     -- user-set target price
    valid_days       INTEGER NOT NULL,     -- how many calendar days alert is valid
    expires_at       TEXT    NOT NULL,     -- created_at + valid_days
    status           TEXT    NOT NULL DEFAULT 'active',
                                           -- active | triggered | expired | deleted
    notes            TEXT,
    created_at       TEXT    NOT NULL,  -- set in Python: datetime.now(IST).isoformat()
    triggered_at     TEXT,              -- IST
    triggered_price  REAL
);

CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_symbol ON alerts(symbol);
```

### 5.5 `candle_cache`

Daily OHLC cache. One row per stock per trading day. Written once, never updated (historical data is immutable).

```sql
CREATE TABLE candle_cache (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    security_id      TEXT    NOT NULL,
    trade_date       TEXT    NOT NULL,  -- YYYY-MM-DD
    open             REAL    NOT NULL,
    high             REAL    NOT NULL,
    low              REAL    NOT NULL,
    close            REAL    NOT NULL,
    volume           INTEGER NOT NULL,
    fetched_at       TEXT    NOT NULL,  -- set in Python: datetime.now(IST).isoformat()

    UNIQUE(security_id, trade_date)     -- one row per stock per day; UNIQUE implicitly creates the index
);
```

**Expected size:** Nifty 500 × ~250 trading days/year × REAL storage ≈ ~500KB per year of history. Storing 5 years for all 500 stocks ≈ ~2.5MB. Negligible for SQLite.

### 5.6 `alert_history`

Append-only audit log for every event on an alert.

```sql
CREATE TABLE alert_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id         INTEGER NOT NULL REFERENCES alerts(id),
    event_type       TEXT    NOT NULL,  -- created|price_check|triggered|expired|deleted|edited
    price            REAL,              -- current price at time of event
    note             TEXT,
    timestamp        TEXT    NOT NULL  -- set in Python: datetime.now(IST).isoformat()
);

CREATE INDEX idx_history_alert_id ON alert_history(alert_id);
```

---

## 6. API Specification

Base URL: `http://localhost:8000/api`

All responses: `Content-Type: application/json`

### 6.1 Config

| Method | Path | Description |
|---|---|---|
| GET | `/config` | Get current config |
| PUT | `/config` | Update config |
| POST | `/config/test-telegram` | Send test Telegram message |
| POST | `/config/test-dhan` | Validate Dhan credentials |

**GET /config response:**
```json
{
  "scan_time": "15:45",
  "scan_percentage": 10.0,
  "scan_days": 4,
  "alert_check_interval_mins": 30,
  "dhan_client_id": "1000000001",
  "dhan_access_token": "ey...abc",        // masked — first 2 + last 3 chars only
  "dhan_access_token_set": true,          // boolean so UI knows a token is stored
  "telegram_bot_token": "12...xyz",       // masked
  "telegram_bot_token_set": true,
  "telegram_chat_id": "-100123456789"
}
```
Note: Full token values are never returned by the API. The UI uses `*_set` booleans to show "configured ✓" vs "not set". When the user re-enters a token, the full new value is sent via PUT and re-encrypted.

### 6.2 Stocks

| Method | Path | Description |
|---|---|---|
| GET | `/stocks?active=true` | List stocks (optional filter) |
| POST | `/stocks` | Add a custom stock |
| PATCH | `/stocks/{id}` | Enable/disable a stock |
| DELETE | `/stocks/{id}` | Remove a stock |
| POST | `/stocks/sync-nifty500` | Re-sync Nifty 500 from Dhan master CSV |
| GET | `/stocks/universes` | List unique universe tags |

### 6.3 Signals (Scanner Results)

| Method | Path | Description |
|---|---|---|
| GET | `/signals?date=2024-01-15` | Signals for a specific date |
| GET | `/signals/dates` | All dates that have at least one signal |
| GET | `/signals/latest` | Most recent scan date's signals |
| POST | `/scanner/run` | Manually trigger scanner now |

**GET /signals?date=2024-01-15 response:**
```json
{
  "date": "2024-01-15",
  "count": 12,
  "params": { "scan_days": 4, "scan_threshold": 10.0 },
  "signals": [
    {
      "id": 1,
      "symbol": "RELIANCE",
      "close_price": 2450.0,
      "start_price": 2200.0,
      "return_pct": 11.36,
      "has_alert": false
    }
  ]
}
```

### 6.4 Alerts

| Method | Path | Description |
|---|---|---|
| GET | `/alerts?status=active` | List alerts (status: active/triggered/expired/deleted/all) |
| POST | `/alerts` | Create a new alert |
| PATCH | `/alerts/{id}` | Edit alert (price, valid_days, notes) |
| DELETE | `/alerts/{id}` | Soft-delete alert |
| GET | `/alerts/{id}/history` | Full event history for one alert |
| GET | `/alerts/history` | All history across all alerts |

**POST /alerts request:**
```json
{
  "symbol": "RELIANCE",
  "security_id": "2885",
  "signal_date": "2024-01-15",
  "alert_price": 2200.00,
  "valid_days": 30,
  "notes": "Waiting for pullback to support"
}
```

### 6.5 Backtest

| Method | Path | Description |
|---|---|---|
| POST | `/backtest` | Run a backtest |

**POST /backtest request:**
```json
{
  "symbol": "RELIANCE",
  "security_id": "2885",
  "from_date": "2023-01-01",
  "to_date": "2024-01-01",
  "pct_threshold": 10.0,
  "num_days": 4
}
```

**Response:**
```json
{
  "symbol": "RELIANCE",
  "from_date": "2023-01-01",
  "to_date": "2024-01-01",
  "total_trading_days": 247,
  "qualifying_days": 8,
  "results": [
    {
      "date": "2023-03-14",
      "close_price": 2450.0,
      "start_price": 2200.0,
      "return_pct": 11.36
    }
  ]
}
```

---

## 7. Dhan API Integration

### 7.1 Authentication

```python
from dhanhq import dhanhq
dhan = dhanhq(client_id="YOUR_CLIENT_ID", access_token="YOUR_TOKEN")
```

### 7.2 Instrument Master (Stock Universe Setup)

Dhan publishes a master CSV of all traded instruments:
- URL: `https://images.dhan.co/api-data/api-scrip-master.csv`
- Filter columns: `SEM_TRADING_SYMBOL`, `SEM_SMST_SECURITY_ID`, `SEM_EXM_EXCH_ID == NSE`, `SEM_INSTRUMENT_NAME == EQUITY`
- Cross-reference with NSE's Nifty 500 list (downloadable from nseindia.com)

On first setup (or when syncing), the app:
1. Downloads Dhan's instrument CSV
2. Downloads NSE's Nifty 500 constituent list
3. Matches symbols to get security IDs
4. Bulk-upserts into `stocks` table

### 7.3 Scanner — Historical Daily Data

For each stock in the universe:
```python
data = dhan.historical_daily_data(
    security_id="2885",
    exchange_segment="NSE_EQ",
    instrument_type="EQUITY",
    from_date="2024-01-01",   # scan_date - 14 calendar days (fixed buffer)
    to_date="2024-01-15"      # scan_date (today, post-15:30 so candle is final)
)
# data returns lists: open[], high[], low[], close[], volume[], timestamp[]
```

**Batching strategy for 500 stocks:**
- Rate limit: 5 req/sec → ~100 seconds for full scan
- Use `asyncio` with a semaphore to fire 5 concurrent requests
- Total scan time: ~100 seconds — perfectly fine for a 3:30 PM background job

### 7.4 Alert Monitor — LTP Batch

The key efficiency insight: Dhan's `/marketfeed/ltp` API accepts up to **1000 instruments in one call**.

```python
# Group active alert securities by exchange segment
payload = {"NSE_EQ": [2885, 1333, 500325, ...]}  # all active alert security IDs
response = dhan.ltp(payload)
# response["data"]["NSE_EQ"]["2885"]["last_price"] = 2441.50
```

This means even with 500 active alerts, alert monitoring is **a single API call** — extremely efficient.

### 7.5 Backtesting — Historical Data Range

```python
data = dhan.historical_daily_data(
    security_id="2885",
    exchange_segment="NSE_EQ",
    instrument_type="EQUITY",
    from_date="2022-12-18",    # from_date - 14 calendar days for lookback buffer
    to_date="2024-01-01"
)
# Full range returned; CandleCacheService serves any already-cached dates
```

All processing happens in-memory in Python — fast, and largely cache-served on repeat runs.

---

## 8. Dhan Token Lifecycle

### 8.1 The Problem

Dhan access tokens are valid for exactly 24 hours (SEBI guideline). Without auto-renewal, every API call fails after expiry and the scanner, alert monitor, and backtest stop working until the user manually pastes a new token.

### 8.2 Chosen Design: Daily Renew at 9:00 AM IST

A `token_renew` scheduler job fires every day at **9:00 AM IST** (15 minutes before market open). It calls Dhan's Renew Token API with the current active token and gets back a fresh 24-hour token.

```
POST https://api.dhan.co/v2/RenewToken
Headers: access-token: <current_token>
         dhanClientId: <client_id>

Response: { "accessToken": "eyJ...", "expiryTime": "..." }
```

**Flow:**
```
9:00 AM IST daily (Mon–Sun)
    TokenService.renew_token()
        → POST /v2/RenewToken
        → success:
            encrypt new token → save to app_config
            update token_expires_at + token_status = 'active'
            re-init DhanService with new token
        → failure (token already expired — machine was off >24h):
            token_status = 'expired'
            DhanService enters degraded mode (backtest serves cached data; scanner/alerts skip)
            send Telegram: "⚠️ Dhan token expired. Paste a new token in Settings to resume."
```

**Key constraint:** `POST /v2/RenewToken` only works on an *active* token. If the app was not running for more than 24 hours, the renewal window is missed and the user must log in to Dhan Web, generate a new token, and paste it into Settings. This is acceptable — a personal trading tool is expected to run daily.

### 8.3 Startup Token Check

On FastAPI startup, before registering any scheduler jobs, the app validates the current token:

```python
async def startup():
    status = await token_service.check_token_validity()
    # GET /v2/profile returns tokenValidity; parse it to determine status

    if status == "expired":
        logger.warning("Dhan token expired — scanner/alerts paused.")
        await telegram_service.send("⚠️ Dhan token expired. Paste a new token in Settings.")
    elif status == "expiring_soon":
        # Token valid but expires within 2 hours — renew immediately rather than waiting for 9 AM
        await token_service.renew_token()
    # status == "active": nothing to do, proceed normally
```

### 8.4 Token Status Tracking

`app_config` stores two fields to surface token health in the UI and at startup:

```sql
token_expires_at    TEXT,     -- IST ISO timestamp from Dhan's expiryTime field
token_status        TEXT NOT NULL DEFAULT 'unknown'
                              -- unknown | active | expiring_soon | expired
```

`expiring_soon` = token expires within the next 2 hours (catches edge cases like startup shortly before 9 AM job fires).

### 8.5 Settings UI — Token Status Card

The Dhan API card in Settings shows:

- Token status badge: `● Active (expires 09:00 IST tomorrow)` / `⚠ Expiring Soon` / `✗ Expired`
- "Renew Now" button — manually triggers `TokenService.renew_token()` immediately
- Access Token field (masked) — allows manual paste of a fresh token if renewal failed

---

## 9. Scheduler Design

Using **APScheduler** embedded in the FastAPI process. Starts when the server starts, persists in-memory.

```
APScheduler
├── Job: token_renew
│   ├── Type: CronTrigger
│   ├── Schedule: Mon-Sun, 09:00 IST  ← daily, 15 min before market open
│   └── Action: TokenService.renew_token()
│
├── Job: daily_scan
│   ├── Type: CronTrigger
│   ├── Schedule: Mon-Fri, 15:45 IST (configurable)          ← 15 min after close
│   └── Action: ScannerService.run_scan()
│
├── Job: alert_monitor
│   ├── Type: IntervalTrigger (every 30 mins)
│   ├── Anchored: 09:15, 09:45, 10:15 … 15:15, 15:45 IST
│   └── Action: AlertService.check_alerts()
│
└── Job: alert_monitor_close            ← dedicated close-time check
    ├── Type: CronTrigger Mon-Fri 15:30 IST
    └── Action: AlertService.check_alerts(bypass_window_guard=True)
```

**IST timezone handling:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo
from datetime import datetime, date

IST = ZoneInfo("Asia/Kolkata")
scheduler = AsyncIOScheduler(timezone=IST)

# Scanner: default 15:45, loaded from config at startup and rescheduled on config change
h, m = map(int, config.scan_time.split(":"))   # e.g. "15:45" → 15, 45
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=h, minute=m, timezone=IST),
                  id="daily_scan", replace_existing=True)

# Alert monitor: interval anchored at 09:15 so ticks land at :15/:45 past each hour
scheduler.add_job(check_alerts, IntervalTrigger(minutes=config.alert_check_interval_mins,
                  start_date=datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0)),
                  id="alert_monitor", replace_existing=True)

# Dedicated close-time check at exactly 15:30 so the final candle is always evaluated
scheduler.add_job(check_alerts, CronTrigger(day_of_week='mon-fri', hour=15, minute=30, timezone=IST),
                  id="alert_monitor_close", replace_existing=True)
```

**Market hours guard inside `check_alerts` (uses configurable bounds):**
```python
def check_alerts(bypass_window_guard: bool = False):
    now = datetime.now(IST)
    if now.weekday() >= 5:                          # skip weekends
        return

    if not bypass_window_guard:
        h_start, m_start = map(int, config.alert_check_start.split(":"))
        h_end,   m_end   = map(int, config.alert_check_end.split(":"))
        window_open  = now.replace(hour=h_start, minute=m_start, second=0, microsecond=0)
        window_close = now.replace(hour=h_end,   minute=m_end,   second=0, microsecond=0)
        # Truncate 'now' to the minute so a cron firing at 15:30:00.003 still passes
        # a window_close of 15:30:00.000. Alternative to truncation is bypass_window_guard.
        if not (window_open <= now.replace(second=0, microsecond=0) <= window_close):
            return

    # proceed with LTP fetch + alert evaluation
```

**Why `bypass_window_guard=True` for the close job:**
The dedicated 15:30 cron job is *intentionally* scheduled to run at close — it doesn't need the window check at all. Passing `bypass_window_guard=True` is cleaner than truncating `now` because it makes the intent explicit: this call is unconditional. The interval job continues to use the guard (with truncated comparison as a belt-and-suspenders fix).

```python
# Interval job — respects the window guard
scheduler.add_job(lambda: check_alerts(bypass_window_guard=False), ..., id="alert_monitor")

# Dedicated close job — bypasses guard; it IS the boundary
scheduler.add_job(lambda: check_alerts(bypass_window_guard=True),
                  CronTrigger(day_of_week='mon-fri', hour=15, minute=30, timezone=IST),
                  id="alert_monitor_close")
```

**Candle cache boundary — why 15:45 matters:**
The `scan_time` default is 15:45 (not 15:30) precisely to let Dhan finalize the day's closing candle. The cache rule "don't cache today's candle during market hours" uses `now > 15:30 IST` as the threshold — the scanner runs after this point, so today's candle is already safe to cache when the scanner fetches it.

**Runtime reschedule example (called by ConfigService on config change):**
```python
def reschedule_scan(new_scan_time: str):
    h, m = map(int, new_scan_time.split(":"))
    scheduler.reschedule_job("daily_scan",
        trigger=CronTrigger(day_of_week='mon-fri', hour=h, minute=m, timezone=IST))

def reschedule_alert_monitor(new_interval_mins: int):
    scheduler.reschedule_job("alert_monitor",
        trigger=IntervalTrigger(minutes=new_interval_mins,
            start_date=datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0)))
```

**Manual trigger:** The `POST /scanner/run` endpoint calls `ScannerService.run_scan()` directly (same function as the scheduled job). Status returned as a JSON response with count of signals found.

---

## 9. Frontend Pages

All pages: React 18 + Vite + Tailwind CSS + shadcn/ui. Light theme. Side navigation.

### 9.1 Dashboard (/)

- Today's scan status (last scan time, # signals found)
- Active alerts count
- Quick stat cards: total signals today, triggered alerts this week
- Recent signals table (last 5)
- Recent alert triggers (last 5)

### 9.2 Signals (/signals)

- Date picker at top (defaults to most recent scan date)
- Shows list of signals for selected date with: Symbol, Return %, Close Price, Start Price, Days
- "Set Alert" button on each row → opens modal to configure `alert_price` and `valid_days`
- Badge on rows that already have an active alert
- "Run Scanner Now" button (calls POST /scanner/run)

### 9.3 Alerts (/alerts)

- Tab bar: Active | Triggered | Expired | All
- Table columns: Symbol, Signal Date, Alert Price, Created, Expires, Status, Triggered Price
- Row actions: Edit (price/days/notes), Delete
- "View History" per alert → slide-out panel showing event log
- Filter/search by symbol

### 9.4 Backtest (/backtest)

- Form:
  - Stock symbol (searchable dropdown from active stocks)
  - Date range: quick presets (Last 3 months, 6 months, 1 year) + custom from/to
  - % threshold (default from config)
  - Number of days (default from config)
  - Submit button
- Results:
  - Summary: "X out of Y trading days qualified"
  - Table of qualifying dates with return %
  - Bar chart / timeline showing qualifying dates on a price chart overlay

### 9.5 Settings (/settings)

Organized in cards:

**Scanner Settings**
- Scan time (time picker)
- % threshold (number input)
- Number of days (number input)

**Stock Universe**
- Table of active stocks with enable/disable toggle
- "Add Stock" button (symbol, security ID, name)
- "Sync Nifty 500" button (re-downloads and merges from Dhan master)
- Universe tag filter

**Dhan API**
- Client ID (text input)
- Access Token (password input with show/hide)
- "Test Connection" button

**Telegram**
- Bot Token (password input)
- Chat ID (text input)
- "Send Test Message" button

---

## 10. Backtesting Engine

### Algorithm Detail

```
Input:
  symbol, security_id
  from_date, to_date         ← the range to test
  pct_threshold              ← e.g. 10.0
  num_days                   ← e.g. 4

Step 1: Fetch candle data
  fetch_from = from_date - 14 calendar days   ← fixed 14-day buffer covers num_days lookback
                                                plus any holiday cluster (Diwali + weekend)
  candles = dhan.historical_daily_data(security_id, fetch_from, to_date)
  # candles is a list of {date, open, high, low, close, volume}
  # (cache-first via CandleCacheService; only uncached ranges hit Dhan API)

Step 2: Find first index >= from_date
  start_idx = first index where candles[i].date >= from_date

Step 3: For each trading day in [from_date, to_date]:
  for i in range(start_idx, len(candles)):
      if i < num_days: continue
      today   = candles[i]
      n_ago   = candles[i - num_days]
      ret_pct = (today.close - n_ago.close) / n_ago.close * 100
      if ret_pct >= pct_threshold:
          results.append({
              date:       today.date,
              close:      today.close,
              start:      n_ago.close,
              return_pct: ret_pct
          })

Output: results list
```

### Why this correctly mirrors the live scanner

The live scanner at 3:30 PM also uses `close[today] - close[N trading days ago]`. The backtest uses the exact same logic on historical closes, so results are directly comparable.

---

## 11. Telegram Notification

### Setup

1. Create a Telegram bot via @BotFather → get bot token
2. Add bot to your channel/group → get chat ID
3. Configure both in Settings page

### Notification format

Uses **HTML parse mode** — avoids the fragility of legacy Markdown where characters like `_`, `*`, `.` in stock symbols or user notes silently break formatting or raise Telegram errors.

```
🔔 <b>Pullback Alert Triggered</b>

Stock: <b>RELIANCE</b>
Signal Date: 15 Jan 2024
Alert Price Set: ₹2,450.00
Current LTP: ₹2,441.50

Checked at: 14:30 IST, 20 Jan 2024
```

### Implementation

```python
import html
import telegram

def _format_alert_message(symbol: str, signal_date: str,
                           alert_price: float, triggered_price: float,
                           checked_at: str) -> str:
    # html.escape() ensures any special chars in symbol/notes don't break the message
    return (
        f"🔔 <b>Pullback Alert Triggered</b>\n\n"
        f"Stock: <b>{html.escape(symbol)}</b>\n"
        f"Signal Date: {html.escape(signal_date)}\n"
        f"Alert Price Set: ₹{alert_price:,.2f}\n"
        f"Current LTP: ₹{triggered_price:,.2f}\n\n"
        f"Checked at: {html.escape(checked_at)}"
    )

async def send_alert(bot_token: str, chat_id: str, message: str):
    bot = telegram.Bot(token=bot_token)
    await bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="HTML"          # HTML is safer than legacy Markdown or MarkdownV2
    )
```

---

## 12. Project Structure

```
pullback/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, startup, CORS, scheduler init
│   │   ├── database.py              # SQLAlchemy engine, session factory, Base
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # AppConfig model
│   │   │   ├── stock.py             # Stock model
│   │   │   ├── signal.py            # ScanSignal model
│   │   │   └── alert.py             # Alert + AlertHistory models
│   │   ├── schemas/
│   │   │   ├── config.py            # Pydantic schemas for config
│   │   │   ├── stock.py
│   │   │   ├── signal.py
│   │   │   ├── alert.py
│   │   │   └── backtest.py
│   │   ├── routers/
│   │   │   ├── config.py            # GET/PUT /config, test endpoints
│   │   │   ├── stocks.py            # Stock CRUD, Nifty500 sync
│   │   │   ├── signals.py           # Signal read + manual scan trigger
│   │   │   ├── alerts.py            # Alert CRUD + history
│   │   │   └── backtest.py          # POST /backtest
│   │   ├── services/
│   │   │   ├── dhan_service.py      # All Dhan API calls, rate limit handling, cache-first OHLC
│   │   │   ├── scanner_service.py   # Scan logic, signal persistence
│   │   │   ├── alert_service.py     # Alert monitoring, status transitions
│   │   │   ├── backtest_service.py  # Backtest engine
│   │   │   ├── telegram_service.py  # Telegram bot wrapper
│   │   │   ├── candle_cache.py      # SQLite candle cache: read/write/gap-detection
│   │   │   ├── encryption.py        # Fernet encrypt/decrypt/mask for credentials
│   │   │   └── token_service.py     # Token renew, TOTP regeneration, expiry checks
│   │   └── scheduler/
│   │       ├── __init__.py
│   │       └── jobs.py              # APScheduler setup and job definitions
│   ├── migrations/
│   │   └── init_db.py               # Create tables, seed default config row
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx                  # Router, layout
│   │   ├── api/
│   │   │   ├── client.js            # Axios instance
│   │   │   ├── signals.js
│   │   │   ├── alerts.js
│   │   │   ├── config.js
│   │   │   ├── stocks.js
│   │   │   └── backtest.js
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Signals.jsx
│   │   │   ├── Alerts.jsx
│   │   │   ├── Backtest.jsx
│   │   │   └── Settings.jsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   └── TopBar.jsx
│   │   │   ├── signals/
│   │   │   │   ├── SignalTable.jsx
│   │   │   │   └── SetAlertModal.jsx
│   │   │   ├── alerts/
│   │   │   │   ├── AlertTable.jsx
│   │   │   │   ├── AlertHistoryPanel.jsx
│   │   │   │   └── EditAlertModal.jsx
│   │   │   └── backtest/
│   │   │       ├── BacktestForm.jsx
│   │   │       └── BacktestResults.jsx
│   │   └── hooks/
│   │       ├── useConfig.js
│   │       ├── useSignals.js
│   │       └── useAlerts.js
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── pullback.db                       # SQLite file (auto-created on first run)
├── backend/.secret_key               # Fernet encryption key (auto-generated, never committed)
└── start.sh                          # Script to start backend + frontend
```

---

## 13. Implementation Plan

### Phase 0: Foundation (Day 1–2)

- [ ] Initialize project structure (backend + frontend scaffolds)
- [ ] Set up SQLAlchemy models and `init_db.py`
- [ ] Seed `app_config` table with defaults
- [ ] Implement `EncryptionService` (Fernet key gen, encrypt/decrypt/mask)
- [ ] Implement `ConfigService` (read/write single row, encrypt on write, mask on read)
- [ ] Implement `TokenService` (check validity via `GET /v2/profile`, renew via `POST /v2/RenewToken`, Telegram alert on expiry)
- [ ] Add `candle_cache` table to schema
- [ ] Basic FastAPI app with CORS and health check endpoint
- [ ] React + Vite + Tailwind scaffold with sidebar layout
- [ ] Add `.secret_key` to `.gitignore`

### Phase 1: Dhan Integration & Stock Universe (Day 3–4)

- [ ] Implement `CandleCacheService` (read, write, gap-detection)
- [ ] Implement `DhanService` with SDK initialization + cache-first `get_daily_ohlc()`
- [ ] Download and parse Dhan master instrument CSV
- [ ] Download NSE Nifty 500 constituent list and cross-reference
- [ ] Seed `stocks` table with Nifty 500 (with security IDs)
- [ ] Stocks API (CRUD + sync endpoint)
- [ ] Settings page: Dhan credentials (masked display + set/update UX) + token status badge + "Renew Now" button + stock universe table

### Phase 2: Scanner (Day 5–7)

- [ ] Implement `ScannerService.run_scan()` with historical data fetch
- [ ] Async batching with rate limit respect (5 req/sec semaphore)
- [ ] Persist signals to `scan_signals`
- [ ] Signals API (list by date, available dates)
- [ ] APScheduler integration (token_renew cron at 09:00 + daily_scan cron at 15:45 + alert_monitor interval + alert_monitor_close cron at 15:30)
- [ ] Startup token validity check with auto-renew and Telegram fallback alert
- [ ] Manual trigger endpoint
- [ ] Scanner Settings UI (scan time, %, days)
- [ ] Signals page with date picker and signal table

### Phase 3: Alerts & Telegram (Day 8–10)

- [ ] Implement `TelegramService`
- [ ] Telegram settings UI with test button
- [ ] Implement `AlertService` (CRUD + status machine)
- [ ] `check_alerts()` with batched LTP call
- [ ] Alert monitor scheduler job (every 30 mins, market hours only)
- [ ] Alerts API (CRUD + history)
- [ ] Alerts page (Active/Triggered/Expired tabs + history panel)
- [ ] "Set Alert" modal on Signals page

### Phase 4: Backtesting (Day 11–13)

- [ ] Implement `BacktestService`
- [ ] Backtest API endpoint
- [ ] Backtest page (form + results table + timeline chart with Recharts)

### Phase 5: Dashboard & Polish (Day 14–15)

- [ ] Dashboard page (stat cards, recent signals, recent triggers)
- [ ] Error handling & toast notifications in UI
- [ ] Loading states and empty states
- [ ] `start.sh` launch script (starts uvicorn + vite dev server)
- [ ] End-to-end smoke test

---

## 14. Architecture Decisions

### ADR-001: Monolithic Backend vs Microservices
**Decision:** Single FastAPI process with APScheduler embedded.
**Rationale:** Single-user standalone app. Microservices would add deploy complexity (multiple processes, inter-service calls, message bus) with zero benefit for this scale.

### ADR-002: SQLite vs PostgreSQL
**Decision:** SQLite.
**Rationale:** Zero ops, no separate server process, single file backup. With <1000 stocks and a single user, SQLite is more than sufficient. Can migrate to Postgres later if needed by just changing the SQLAlchemy connection string.

### ADR-003: APScheduler vs Celery vs OS cron
**Decision:** APScheduler embedded in FastAPI.
**Rationale:** Celery requires a Redis/RabbitMQ broker — unnecessary overhead. OS cron requires the user to manage cron jobs separately. APScheduler runs inside the app, starts/stops with it, and is configurable at runtime from the Settings page.

### ADR-004: LTP vs WebSocket for alert monitoring
**Decision:** Poll LTP every 30 minutes via REST API.
**Rationale:** Dhan's WebSocket (Live Market Feed) is designed for continuous streaming and is harder to manage lifecycle for 500 stocks. Since the requirement is 30-minute checks (not millisecond), REST polling is simpler and well within Dhan's rate limits (1 call per batch, unlimited quote calls per day).

### ADR-005: React vs Vue vs plain HTML
**Decision:** React + Vite.
**Rationale:** Ecosystem richness (shadcn/ui, Recharts, React Query), TypeScript-friendly, good tooling. The UI complexity (modals, tabs, charts, async data) warrants a proper framework.

### ADR-006: Credential Encryption — Fernet vs OS Keychain vs plaintext
**Decision:** Fernet symmetric encryption (Python `cryptography` library), key stored in a local `.secret_key` file.
**Rationale:**
- Plaintext in SQLite is unacceptable — anyone with file access sees all tokens.
- OS keychain (macOS Keychain, libsecret) would be the most secure option but requires platform-specific code and makes the app harder to run on Linux/Windows. Out of scope for a standalone personal tool.
- Fernet is simple, battle-tested, and cross-platform. The `.secret_key` file is gitignored and stays on the user's machine alongside the database.
- **Trade-off:** If the `.secret_key` file is deleted, credentials must be re-entered. This is acceptable — document it clearly.

### ADR-007: Candle Cache — SQLite table vs file-based cache vs no cache

**Decision:** SQLite `candle_cache` table.
**Rationale:**
- No cache means every backtest on the same stock burns Dhan API quota and adds latency. With a 100,000/day limit on Data APIs, scanning 500 stocks daily already uses 500 calls; frequent backtesting without a cache would eat into this.
- File-based cache (pickle, Parquet) is faster for bulk reads but requires a separate file management system alongside the DB.
- SQLite table is the natural choice: same file, same backup, same ORM, and indexed queries on `(security_id, trade_date)` are fast for the data sizes involved.
- **Cache invalidation:** Historical OHLC never changes, so no invalidation needed. Only today's partial candle is excluded during market hours.

### ADR-008: Scan time default 15:45, not 15:30
**Decision:** Default `scan_time` is 15:45 IST.
**Rationale:** Market closes at 15:30. Dhan's daily closing candle needs a few minutes to be finalized and available via the historical API. Firing the scanner at 15:30:00 sharp risks fetching an incomplete or missing candle for the current day. 15:45 gives a 15-minute buffer. Users can change this in Settings, but the default is intentionally conservative. The candle cache "don't cache today's candle during market hours" guard also uses 15:30 as its threshold, so by 15:45 the cache rule has already lifted.

### ADR-009: Dedicated 15:30 alert check in addition to interval job
**Decision:** Two alert monitor jobs: an `IntervalTrigger` anchored at 09:15 (fires :15/:45 past hour) + a `CronTrigger` at exactly 15:30.
**Rationale:** An `IntervalTrigger(minutes=30)` anchored at 09:15 produces ticks at 09:15, 09:45, …, 15:15. The 15:30 market close — the most important moment to check alerts before the day ends — is never hit. The dedicated close-time cron job closes this gap without changing the interval logic.

### ADR-010: Timestamp convention — IST throughout
**Decision:** All timestamps written to SQLite use `datetime.now(IST)` in Python. No SQLite `datetime('now')` defaults.
**Rationale:** `datetime('now')` in SQLite returns UTC. For a system operating in Indian markets, mixing UTC wall-clock times with IST `scan_date` date strings causes off-by-one-day bugs for operations that happen after 18:30 IST (midnight UTC). Enforcing IST at the application layer is simple and eliminates the ambiguity. The convention is documented here so future developers don't introduce UTC writes.

### ADR-011: Backtest lookback buffer — fixed 14 calendar days
**Decision:** Always fetch `from_date - 14 calendar days` as the pre-range lookback, regardless of `num_days`.
**Rationale:** A variable buffer like `num_days * 2` calendar days fails around long Indian holiday clusters (e.g., Diwali week + surrounding weekends can consume 7–8 calendar days with no trading). 14 calendar days guarantees at least 8–9 trading days of lookback, which covers `num_days` up to 8 with margin. Simple, predictable, and the extra days are either served from cache (free) or fetched once and cached.

### ADR-013: Dhan Token Renewal Strategy
**Decision:** Daily `POST /v2/RenewToken` at 9:00 AM IST. No TOTP mode. Manual re-entry via Settings if the renewal window is missed.
**Rationale:**
- Tokens expire every 24 hours (SEBI mandate); manual re-entry every day is unacceptable UX.
- `POST /v2/RenewToken` requires only the current active token — no additional secrets stored. One API call, zero new credentials.
- TOTP mode (the only alternative that survives >24h downtime) requires storing the user's Dhan login PIN on disk. That is the credential to the entire trading account. The security trade-off outweighs the convenience gain for a personal tool expected to run daily.
- The OAuth API key flow was rejected: its Step 2 requires a browser redirect with human login — not automatable in a background service.
- 9:00 AM IST (15 minutes before market open) was chosen over an off-hours time so the renewal happens when the user is likely awake and able to respond to a Telegram expiry alert quickly if needed.
- On startup the app always calls `GET /v2/profile` to check `tokenValidity` and renews proactively if the token is within 2 hours of expiry.

### ADR-012: Telegram HTML parse mode over Markdown
**Decision:** Use `parse_mode="HTML"` with `html.escape()` on all user-supplied content.
**Rationale:** Telegram's legacy `Markdown` mode silently mangles messages containing `_`, `*`, `` ` ``, or `[`. `MarkdownV2` requires escaping 18 special characters — easy to miss. HTML mode requires only `<`, `>`, `&` to be escaped (handled by `html.escape()`), is explicit, and produces identical visual output. Any stock symbol or user note can be safely interpolated.

---

## 15. Confirmed Decisions & Assumptions

### Confirmed Clarifications

| # | Question | Answer |
|---|---|---|
| 1 | Alert trigger direction | **`LTP <= alert_price`** — triggers when price pulls back down to your target entry |
| 2 | "4 days including current day" | **Confirmed** — uses 4 trading days via Dhan daily candle data (weekends/holidays handled automatically) |
| 3 | Nifty 500 sync | **Manual sync only** — "Sync Nifty 500" button in Settings; no auto-resync needed |
| 4 | Multiple alerts per signal | **Yes allowed** — each alert is an independent row; user can set multiple price levels for the same stock |
| 5 | Scanner on market holiday | **Skip gracefully** — if Dhan returns no data for today, scanner writes no signals and logs the skip |

### Confirmed New Features

| Feature | Design |
|---|---|
| **Credential encryption** | Dhan access token + Telegram bot token encrypted with Fernet AES-128 at rest in SQLite. Key stored in `backend/.secret_key` (gitignored). API returns masked values only. |
| **Candle data caching** | All daily OHLC fetched from Dhan (scanner + backtest) stored in `candle_cache` SQLite table. On any subsequent request for the same stock+date range, cached rows are returned directly; only missing date gaps hit the Dhan API. Today's candle excluded from cache during market hours. |

### Assumptions Made

- Indian market hours: 9:15 AM – 3:30 PM IST, Monday–Friday
- Alert check every 30 minutes between 9:15 AM and 3:30 PM IST only
- Return calculation uses **closing prices only** (daily timeframe), not intraday prices
- The app runs on a Mac/Linux machine (for `start.sh`)
- One user, one Telegram channel — no multi-user auth needed
- Dhan access token is long-lived (configured once in settings); if it expires, user re-enters it
- `.secret_key` file loss = credentials must be re-entered (acceptable for personal standalone tool)
