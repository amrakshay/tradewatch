# TradeWatch — Opening Range Breakout (ORB) Strategy Architecture

> Extends the existing pullback strategy architecture. Read `ARCHITECTURE.md` first for shared components (DhanService, TelegramService, ConfigService, CandleCacheService, APScheduler setup).

---

## Table of Contents

1. [Strategy Overview](#1-strategy-overview)
2. [Signal Logic](#2-signal-logic)
3. [Database Schema — New Tables](#3-database-schema--new-tables)
4. [New & Extended Services](#4-new--extended-services)
5. [API Specification](#5-api-specification)
6. [Scheduler Design](#6-scheduler-design)
7. [Telegram Notifications](#7-telegram-notifications)
8. [Backtesting Engine](#8-backtesting-engine)
9. [Frontend Pages](#9-frontend-pages)
10. [Implementation Task Index](#10-implementation-task-index)
11. [Architecture Decisions](#11-architecture-decisions)

---

## 1. Strategy Overview

Opening Range Breakout (ORB) is an intraday strategy that:

1. Establishes the **opening range** as the high and low of the first 15 minutes of trading (9:15–9:30 AM IST, covering 3 five-minute candles)
2. Evaluates the **first 5-min candle** (9:15–9:20 AM) for strength and volume
3. Watches all day (until 3:30 PM IST) for a **breakout** above the range high (Long signal) or below the range low (Short signal), confirmed by a volume surge on the breakout candle
4. Fires a **Telegram notification** immediately when a signal is detected
5. Stores all signal details for later review and backtesting

**Key differences from pullback strategy:**

| | Pullback | ORB |
|---|---|---|
| Timeframe | Daily OHLC | 5-min intraday |
| Scan time | Once at 15:45 IST | Every 5 mins, 9:25–15:30 IST |
| Universe | Nifty 500 stocks | Configurable indices/stocks |
| Output | Daily signals → user sets alert | Signal fires + Telegram immediately |
| Alert concept | Price alert with expiry | None — Telegram at signal time |

---

## 2. Signal Logic

### 2.1 Criterion 1 — Strong First 5-Min Candle

Evaluated at **9:25 AM IST** (after the 9:15–9:20 candle closes).

**Bullish first candle:** `close > open`
**Bearish first candle:** `close < open`

**Strong candle (body ratio):**
```
body_pct = |close - open| / (high - low)
strong = body_pct >= orb_body_pct_threshold   # default 0.6
```
A body ≥ 60% of the total wick range filters out indecision/doji candles.

**High volume:**
```
prev_day_2nd_half_avg_vol = avg(5-min candle volumes from 12:45–15:25 IST, previous trading day)
volume_ratio = first_candle_volume / prev_day_2nd_half_avg_vol
high_volume = volume_ratio >= orb_volume_ratio_threshold   # default 1.5
```
"Second half" = roughly 12:45 PM onward (~33 candles). This represents settled, non-reactive institutional volume — a standard ORB benchmark.

> **Note:** Criterion 1 is informational and stored with the signal, but does NOT gate the breakout check. A breakout signal can still fire even if the first candle is not "strong". The strength flags are stored so the user can filter/review.

### 2.2 Criterion 2 — 15-Min Opening Range

Established at **9:30 AM IST** (after three 5-min candles: 9:15, 9:20, 9:25 close).

```
orb_high = max(high of 9:15 candle, 9:20 candle, 9:25 candle)
orb_low  = min(low  of 9:15 candle, 9:20 candle, 9:25 candle)
```

### 2.3 Criterion 3 — Breakout Candle Closes Beyond Range, with Volume Surge

Checked on every 5-min candle from **9:35 AM** onwards until **3:30 PM IST**.

**We wait for the breakout candle to fully CLOSE beyond the ORB level — not just touch or wick through it.** A wick above the range that pulls back and closes inside is NOT a signal. Only a confirmed close above/below removes ambiguity and avoids false signals from intraday noise.

**Long signal (candle closes above ORB high):**
```
candle.close > orb_high  AND  candle.volume > previous_candle.volume
```
> Checking `close` (not `high`) means the candle must sustain the move through the full 5-min period and close above the range. A wick that pokes above orb_high mid-candle and retreats does not trigger.

**Short signal (candle closes below ORB low):**
```
candle.close < orb_low  AND  candle.volume > previous_candle.volume
```
> Same logic: close (not low) must be below the range.

- Both Long and Short signals are independent — both can fire on the same day
- Each direction fires **at most once per instrument per day** (first qualifying candle wins)
- Signal is stored immediately and Telegram notification sent

### 2.4 Daily Flow

```
09:15  Market opens. ORB monitor wakes up.
09:25  First candle (9:15–9:20) closed. Evaluate Criterion 1. Fetch prev-day 2nd-half volume.
09:30  Second candle (9:20–9:25) closed.
09:35  Third candle (9:25–9:30) closed → ORB range established (Criterion 2).
       Begin checking each new candle for breakout (Criterion 3).
       ...
15:30  Last check. Market closes. ORB monitor stops.
```

---

## 3. Database Schema — New Tables

### 3.1 `orb_universe`

Instruments tracked for ORB. Configurable from Settings UI.

```sql
CREATE TABLE orb_universe (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT    NOT NULL,            -- e.g. "NIFTY 50", "BANKNIFTY"
    security_id      TEXT    NOT NULL UNIQUE,      -- Dhan security ID, e.g. "13"
    exchange_segment TEXT    NOT NULL DEFAULT 'IDX_I',  -- IDX_I for index, NSE_EQ for equity
    instrument_type  TEXT    NOT NULL DEFAULT 'INDEX',  -- INDEX or EQUITY
    is_active        INTEGER NOT NULL DEFAULT 1,
    added_at         TEXT    NOT NULL   -- datetime.now(IST).isoformat()
);

CREATE INDEX idx_orb_universe_active ON orb_universe(is_active);
```

Default seed rows (on first run):
- NIFTY 50: security_id=`13`, segment=`IDX_I`, instrument=`INDEX`
- BANKNIFTY: security_id=`25`, segment=`IDX_I`, instrument=`INDEX`

### 3.2 `orb_signals`

One row per signal. Max 2 per instrument per day (one Long, one Short).

```sql
CREATE TABLE orb_signals (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_date               TEXT    NOT NULL,   -- YYYY-MM-DD

    -- Instrument
    symbol                    TEXT    NOT NULL,
    security_id               TEXT    NOT NULL,

    -- Criterion 1: First 5-min candle (9:15–9:20)
    first_candle_open         REAL    NOT NULL,
    first_candle_high         REAL    NOT NULL,
    first_candle_low          REAL    NOT NULL,
    first_candle_close        REAL    NOT NULL,
    first_candle_volume       INTEGER NOT NULL,
    first_candle_direction    TEXT    NOT NULL,   -- bullish | bearish
    first_candle_body_pct     REAL    NOT NULL,   -- |close-open|/(high-low), 0.0–1.0
    first_candle_volume_ratio REAL    NOT NULL,   -- vs prev day 2nd-half avg
    first_candle_strong       INTEGER NOT NULL,   -- 1 if both body_pct and volume_ratio pass thresholds
    prev_day_avg_volume       REAL    NOT NULL,   -- avg 5-min volume 12:45–15:25 prev day

    -- Criterion 2: Opening range
    orb_high                  REAL    NOT NULL,
    orb_low                   REAL    NOT NULL,

    -- Criterion 3: Breakout
    signal_direction          TEXT    NOT NULL,   -- LONG | SHORT
    breakout_time             TEXT    NOT NULL,   -- IST "HH:MM" of breakout candle open
    breakout_candle_open      REAL    NOT NULL,
    breakout_candle_high      REAL    NOT NULL,
    breakout_candle_low       REAL    NOT NULL,
    breakout_candle_close     REAL    NOT NULL,
    breakout_candle_volume    INTEGER NOT NULL,
    prev_candle_volume        INTEGER NOT NULL,   -- volume of candle before breakout

    signal_price              REAL    NOT NULL,   -- breakout candle close (entry reference)
    telegram_sent             INTEGER NOT NULL DEFAULT 0,
    created_at                TEXT    NOT NULL,   -- datetime.now(IST).isoformat()

    UNIQUE(signal_date, security_id, signal_direction)
);

CREATE INDEX idx_orb_signals_date     ON orb_signals(signal_date);
CREATE INDEX idx_orb_signals_symbol   ON orb_signals(symbol);
CREATE INDEX idx_orb_signals_dir      ON orb_signals(signal_direction);
```

### 3.3 `intraday_candle_cache`

5-min OHLC cache (same cache-first pattern as `candle_cache` for daily data).

```sql
CREATE TABLE intraday_candle_cache (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    security_id      TEXT    NOT NULL,
    trade_date       TEXT    NOT NULL,   -- YYYY-MM-DD
    candle_time      TEXT    NOT NULL,   -- "HH:MM" IST (candle open time)
    interval_mins    INTEGER NOT NULL DEFAULT 5,
    open             REAL    NOT NULL,
    high             REAL    NOT NULL,
    low              REAL    NOT NULL,
    close            REAL    NOT NULL,
    volume           INTEGER NOT NULL,
    fetched_at       TEXT    NOT NULL,   -- datetime.now(IST).isoformat()

    UNIQUE(security_id, trade_date, candle_time, interval_mins)
);

CREATE INDEX idx_intraday_cache_lookup ON intraday_candle_cache(security_id, trade_date, interval_mins);
```

**Cache behavior:**
- Past dates: cached permanently (historical intraday data doesn't change)
- Today's candles: cached as they arrive; a candle is only cached after it has closed (i.e., fetched at or after its close time)
- Cache is keyed on `(security_id, trade_date, candle_time, interval_mins)` — future strategies using other intervals (1-min, 15-min) can reuse the same table

### 3.4 `app_config` additions

Two new columns added via Alembic migration:

```sql
ALTER TABLE app_config ADD COLUMN orb_body_pct_threshold    REAL NOT NULL DEFAULT 0.6;
ALTER TABLE app_config ADD COLUMN orb_volume_ratio_threshold REAL NOT NULL DEFAULT 1.5;
```

---

## 4. New & Extended Services

### 4.1 DhanService — `get_intraday_5min()`

New method on the existing `DhanService`. Uses Dhan's `/charts/intraday` endpoint with `interval=5`.

```python
async def get_intraday_5min(
    self,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: date,
    to_date: date
) -> list[IntradayCandle]:
    """
    Returns 5-min candles for the given date range, cache-first via IntradayCacheService.
    Candles are sorted ascending by candle_time.
    """
```

**Dhan API call:**
```python
POST /v2/charts/intraday
{
    "securityId": security_id,
    "exchangeSegment": exchange_segment,
    "instrument": instrument_type,
    "interval": "5",
    "fromDate": "YYYY-MM-DD 09:15:00",
    "toDate": "YYYY-MM-DD 15:30:00"
}
```

Response timestamps are Unix epoch (IST). Convert to `HH:MM` strings for cache storage.

**Rate limit:** Same data API limit as daily (5 req/sec, 100k/day). For ORB with 2–5 instruments, calls are minimal.

### 4.2 IntradayCacheService

Mirrors `CandleCacheService` but for the `intraday_candle_cache` table.

```python
class IntradayCacheService:
    def get_cached_candles(self, security_id, trade_date, interval_mins=5) -> list[IntradayCandle]
    def store_candles(self, security_id, trade_date, candles: list[IntradayCandle], interval_mins=5)
    def get_missing_dates(self, security_id, from_date, to_date, interval_mins=5) -> list[date]
```

**Cache-first flow for `get_intraday_5min()`:**
```
1. Query intraday_candle_cache for all rows where security_id=X AND trade_date in range AND interval=5
2. Find which dates in the range have no cached rows
3. For each missing date: call Dhan intraday API, store results
4. Return merged sorted candle list
```

Today's candles: cache only candles whose close time has passed (e.g., a 9:15 candle closes at 9:20 — only cache it if `now > 9:20 IST`). During live polling this is handled naturally since we fetch and process the latest closed candle.

### 4.3 ORBScannerService

Core ORB logic. Called by the scheduler every 5 minutes and by the backtest engine.

```python
class ORBScannerService:

    async def run_orb_check(self) -> list[ORBSignal]:
        """
        Called every 5 mins by scheduler. Processes all active orb_universe instruments.
        Skips weekends, skips if before 9:25 or after 15:30.
        """
        now = datetime.now(IST)
        if now.weekday() >= 5:
            return []
        if now < now.replace(hour=9, minute=25, second=0):
            return []
        if now > now.replace(hour=15, minute=30, second=0):
            return []

        instruments = db.query(ORBUniverse).filter_by(is_active=True).all()
        new_signals = []
        for inst in instruments:
            signals = await self._process_instrument(inst, now.date())
            new_signals.extend(signals)
        return new_signals

    async def _process_instrument(self, instrument, today) -> list[ORBSignal]:
        # 1. Fetch today's 5-min candles (cache-first)
        candles = await dhan_service.get_intraday_5min(
            instrument.security_id, instrument.exchange_segment,
            instrument.instrument_type, today, today
        )
        if len(candles) < 1:
            return []

        # 2. Evaluate first candle (9:15 candle)
        first = candles[0]
        body_pct = abs(first.close - first.open) / (first.high - first.low) if (first.high - first.low) > 0 else 0
        direction = "bullish" if first.close >= first.open else "bearish"
        prev_day_avg_vol = await self._get_prev_day_2nd_half_avg_volume(instrument, today)
        volume_ratio = first.volume / prev_day_avg_vol if prev_day_avg_vol > 0 else 0
        strong = body_pct >= config.orb_body_pct_threshold and volume_ratio >= config.orb_volume_ratio_threshold

        # 3. Need at least 3 candles (9:15, 9:20, 9:25) for range
        if len(candles) < 3:
            return []

        orb_high = max(c.high for c in candles[:3])
        orb_low  = min(c.low  for c in candles[:3])

        # 4. Check for breakouts on candles[3:] (9:35 AM onwards)
        new_signals = []
        existing_long  = db.query(ORBSignal).filter_by(signal_date=today, security_id=instrument.security_id, signal_direction="LONG").first()
        existing_short = db.query(ORBSignal).filter_by(signal_date=today, security_id=instrument.security_id, signal_direction="SHORT").first()

        for i in range(3, len(candles)):
            candle = candles[i]
            prev   = candles[i - 1]

            if not existing_long and candle.close > orb_high and candle.volume > prev.volume:
                sig = self._save_signal("LONG", today, instrument, first, body_pct, direction,
                                        volume_ratio, strong, prev_day_avg_vol, orb_high, orb_low,
                                        candle, prev)
                await telegram_service.send_orb_signal(sig)
                existing_long = sig
                new_signals.append(sig)

            if not existing_short and candle.close < orb_low and candle.volume > prev.volume:
                sig = self._save_signal("SHORT", today, instrument, first, body_pct, direction,
                                        volume_ratio, strong, prev_day_avg_vol, orb_high, orb_low,
                                        candle, prev)
                await telegram_service.send_orb_signal(sig)
                existing_short = sig
                new_signals.append(sig)

        return new_signals

    async def _get_prev_day_2nd_half_avg_volume(self, instrument, today) -> float:
        """
        Fetches the previous trading day's 5-min candles (cache-first),
        filters candles from 12:45 PM onwards, returns average volume.
        """
        prev_day = self._prev_trading_day(today)
        candles = await dhan_service.get_intraday_5min(
            instrument.security_id, instrument.exchange_segment,
            instrument.instrument_type, prev_day, prev_day
        )
        second_half = [c for c in candles if c.candle_time >= "12:45"]
        if not second_half:
            return 0.0
        return sum(c.volume for c in second_half) / len(second_half)
```

### 4.4 TelegramService — `send_orb_signal()`

New method on existing `TelegramService`:

```python
def _format_orb_signal(signal: ORBSignal) -> str:
    direction_emoji = "🟢" if signal.signal_direction == "LONG" else "🔴"
    strength_badge = "⚡ Strong Setup" if signal.first_candle_strong else "〰 Weak Setup"
    return (
        f"{direction_emoji} <b>ORB Signal: {html.escape(signal.symbol)}</b>\n\n"
        f"Direction: <b>{signal.signal_direction}</b> ({strength_badge})\n"
        f"Signal Price: <b>₹{signal.signal_price:,.2f}</b>\n"
        f"Breakout Time: {signal.breakout_time} IST\n\n"
        f"Opening Range: ₹{signal.orb_low:,.2f} – ₹{signal.orb_high:,.2f}\n"
        f"Breakout Volume: {signal.breakout_candle_volume:,} "
        f"(prev: {signal.prev_candle_volume:,})\n\n"
        f"First Candle ({signal.first_candle_direction.title()}): "
        f"body {signal.first_candle_body_pct:.0%}, "
        f"vol ratio {signal.first_candle_volume_ratio:.1f}×\n"
        f"Date: {signal.signal_date}"
    )
```

---

## 5. API Specification

Base URL: `http://localhost:8000/api/orb`

### 5.1 ORB Universe (instrument management)

| Method | Path | Description |
|---|---|---|
| GET | `/orb/universe` | List all ORB instruments |
| POST | `/orb/universe` | Add an instrument |
| PATCH | `/orb/universe/{id}` | Enable/disable |
| DELETE | `/orb/universe/{id}` | Remove |

**POST /orb/universe request:**
```json
{
  "symbol": "BANKNIFTY",
  "security_id": "25",
  "exchange_segment": "IDX_I",
  "instrument_type": "INDEX"
}
```

### 5.2 ORB Signals

| Method | Path | Description |
|---|---|---|
| GET | `/orb/signals?date=2024-01-15` | Signals for a specific date |
| GET | `/orb/signals/dates` | All dates with at least one ORB signal |
| GET | `/orb/signals/latest` | Today's (or most recent) signals |
| POST | `/orb/scanner/run` | Manually trigger ORB check now |

**GET /orb/signals?date=2024-01-15 response:**
```json
{
  "date": "2024-01-15",
  "count": 2,
  "signals": [
    {
      "id": 1,
      "symbol": "NIFTY 50",
      "signal_direction": "LONG",
      "breakout_time": "10:05",
      "signal_price": 22150.75,
      "orb_high": 22130.00,
      "orb_low": 21980.00,
      "first_candle_strong": true,
      "first_candle_body_pct": 0.72,
      "first_candle_volume_ratio": 1.8,
      "breakout_candle_volume": 125000,
      "prev_candle_volume": 82000,
      "created_at": "2024-01-15T10:05:32+05:30"
    }
  ]
}
```

### 5.3 ORB Settings

| Method | Path | Description |
|---|---|---|
| GET | `/config` | Includes `orb_body_pct_threshold`, `orb_volume_ratio_threshold` |
| PUT | `/config` | Update thresholds (existing endpoint, new fields) |

### 5.4 ORB Backtest

| Method | Path | Description |
|---|---|---|
| POST | `/orb/backtest` | Run ORB backtest over a date range |

**POST /orb/backtest request:**
```json
{
  "symbol": "NIFTY 50",
  "security_id": "13",
  "exchange_segment": "IDX_I",
  "instrument_type": "INDEX",
  "from_date": "2024-01-01",
  "to_date": "2024-06-30",
  "body_pct_threshold": 0.6,
  "volume_ratio_threshold": 1.5
}
```

**Response:**
```json
{
  "symbol": "NIFTY 50",
  "from_date": "2024-01-01",
  "to_date": "2024-06-30",
  "total_trading_days": 123,
  "days_with_long_signal": 34,
  "days_with_short_signal": 28,
  "days_with_strong_setup": 19,
  "results": [
    {
      "date": "2024-01-15",
      "orb_high": 22130.00,
      "orb_low": 21980.00,
      "first_candle_direction": "bullish",
      "first_candle_strong": true,
      "first_candle_body_pct": 0.72,
      "first_candle_volume_ratio": 1.8,
      "long_signal": {
        "breakout_time": "10:05",
        "signal_price": 22150.75,
        "breakout_candle_volume": 125000,
        "prev_candle_volume": 82000
      },
      "short_signal": null
    }
  ]
}
```

---

## 6. Scheduler Design

New APScheduler job added to existing scheduler setup in `backend/app/scheduler/jobs.py`:

```python
# ORB monitor: every 5 mins, 09:25–15:30 IST, Mon–Fri
scheduler.add_job(
    orb_scanner_service.run_orb_check,
    IntervalTrigger(
        minutes=5,
        start_date=datetime.now(IST).replace(hour=9, minute=25, second=0, microsecond=0),
        timezone=IST
    ),
    id="orb_monitor",
    replace_existing=True
)
```

**Market hours guard inside `run_orb_check`:**
```python
now = datetime.now(IST)
if now.weekday() >= 5:
    return   # skip weekends
open_time  = now.replace(hour=9,  minute=25, second=0, microsecond=0)
close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
if not (open_time <= now <= close_time):
    return   # outside market window
```

**Total active jobs after ORB addition:**

| Job ID | Type | Schedule | Action |
|---|---|---|---|
| `token_renew` | CronTrigger | Mon–Sun 09:00 IST | TokenService.renew_token() |
| `daily_scan` | CronTrigger | Mon–Fri 15:45 IST | ScannerService.run_scan() |
| `alert_monitor` | IntervalTrigger | every 30 mins | AlertService.check_alerts() |
| `alert_monitor_close` | CronTrigger | Mon–Fri 15:30 IST | AlertService.check_alerts(bypass=True) |
| `orb_monitor` | IntervalTrigger | every 5 mins, 09:25 IST | ORBScannerService.run_orb_check() |

---

## 7. Telegram Notifications

**ORB Long example:**
```
🟢 ORB Signal: NIFTY 50

Direction: LONG (⚡ Strong Setup)
Signal Price: ₹22,150.75
Breakout Time: 10:05 IST

Opening Range: ₹21,980.00 – ₹22,130.00
Breakout Volume: 1,25,000 (prev: 82,000)

First Candle (Bullish): body 72%, vol ratio 1.8×
Date: 15 Jan 2024
```

**ORB Short example:**
```
🔴 ORB Signal: BANKNIFTY

Direction: SHORT (〰 Weak Setup)
Signal Price: ₹47,890.00
Breakout Time: 11:25 IST

Opening Range: ₹47,950.00 – ₹48,210.00
Breakout Volume: 98,000 (prev: 61,000)

First Candle (Bearish): body 45%, vol ratio 1.1×
Date: 15 Jan 2024
```

---

## 8. Backtesting Engine

### Algorithm

```
Input:
  symbol, security_id, exchange_segment, instrument_type
  from_date, to_date
  body_pct_threshold, volume_ratio_threshold

For each trading day D in [from_date, to_date]:

  Step 1: Fetch 5-min candles for day D (cache-first via IntradayCacheService)
  Step 2: Fetch prev trading day's 5-min candles (cache-first)

  Step 3: Evaluate first candle (9:15 candle)
    body_pct     = |close - open| / (high - low)
    prev_avg_vol = avg volume of prev day candles with time >= "12:45"
    volume_ratio = first_candle_volume / prev_avg_vol
    strong       = body_pct >= threshold AND volume_ratio >= vol_threshold

  Step 4: Establish range from first 3 candles
    orb_high = max(high[:3])
    orb_low  = min(low[:3])

  Step 5: Scan candles[3:] for breakouts
    For each candle i (index 3 onward):
      if close > orb_high AND volume > candles[i-1].volume → record LONG
      if close < orb_low  AND volume > candles[i-1].volume → record SHORT

  Append result for day D with: range, first candle data, long/short signal (if any)

Output: list of per-day results
```

**Data volume for backtest:**
- 6 months of 5-min data for one instrument ≈ 125 trading days × ~75 candles/day = ~9,400 candles
- All served from cache after first fetch; Dhan allows 90 days per request so a 6-month backtest needs 2 API calls

---

## 9. Frontend Pages

### 9.1 ORB Signals Page (`/orb/signals`)

- Date picker (defaults to today or most recent date with signals)
- Per-instrument signal cards showing:
  - Direction badge (LONG 🟢 / SHORT 🔴)
  - Signal price and breakout time
  - Opening range (high–low)
  - First candle summary: direction, body %, volume ratio, strong badge
  - Breakout volume vs previous candle volume
- "Run ORB Check Now" button (calls POST /orb/scanner/run)
- Empty state: "No signals for this date" with reason (no breakout / market closed)

### 9.2 ORB Backtest Page (`/orb/backtest`)

- Form:
  - Instrument dropdown (from orb_universe)
  - Date range (quick presets: 1 month, 3 months, 6 months + custom)
  - Body % threshold (default from config)
  - Volume ratio threshold (default from config)
  - Submit button
- Results:
  - Summary stats: total days, long signals count, short signals count, strong-setup days
  - Table: date, ORB range, first candle strength, Long signal time+price, Short signal time+price
  - Filter toggle: "Show only strong setups"

### 9.3 Settings Page — ORB section (extends existing `/settings`)

New card in existing Settings page:

**ORB Strategy**
- Body % threshold (number input, 0.0–1.0, default 0.6)
- Volume ratio threshold (number input, default 1.5)
- ORB Universe table: Symbol | Security ID | Exchange | Type | Active toggle | Delete
- "Add Instrument" button → modal with fields: Symbol, Security ID, Exchange Segment, Instrument Type

---

## 10. Implementation Task Index

| ID | Task | Depends On |
|----|------|-----------|
| T23 | DB schema: `orb_universe`, `orb_signals`, `intraday_candle_cache`, `app_config` columns | T02 |
| T24 | `IntradayCacheService` + `DhanService.get_intraday_5min()` | T07, T08 |
| T25 | `ORBScannerService` core logic | T24 |
| T26 | ORB scheduler job (`orb_monitor`) | T14, T25 |
| T27 | ORB API routers (`/orb/universe`, `/orb/signals`, `/orb/scanner/run`) | T25 |
| T28 | ORB backtest service + `POST /orb/backtest` endpoint | T24 |
| T29 | TelegramService ORB notification | T11, T25 |
| T30 | Frontend: ORB Signals page, ORB Backtest page, Settings ORB section | T16, T27, T28 |

---

## 11. Architecture Decisions

### ORB-ADR-001: Criterion 1 is informational, not a gate

**Decision:** The strong-first-candle check (body ratio + volume) is stored and displayed but does NOT prevent a breakout signal from firing.

**Rationale:** ORB breakouts in practice often occur even when the opening candle is weak. Gating on criterion 1 would suppress real breakouts. Instead, the UI shows a "Strong Setup" vs "Weak Setup" badge so the user can judge quality, and the backtest lets them filter by strength.

### ORB-ADR-002: Intraday candle cache uses a separate table, not `candle_cache`

**Decision:** New `intraday_candle_cache` table keyed on `(security_id, trade_date, candle_time, interval_mins)`.

**Rationale:** Daily and intraday candles have fundamentally different schemas (daily has no `candle_time`; intraday has no natural `trade_date` without derivation). Mixing them in one table would require nullable columns and complex queries. A dedicated table is cleaner and allows future strategies to use other intervals (1-min, 15-min) via the same `interval_mins` column.

### ORB-ADR-003: Second half of previous day defined as 12:45 PM onwards

**Decision:** `prev_day_2nd_half_avg_vol` uses candles with `candle_time >= "12:45"`.

**Rationale:** The trading session runs 9:15–15:30 (6h15m). The midpoint is ~12:22. Using 12:45 gives a clean, round cutoff that captures the afternoon session (~33 candles). This avoids the volatile first hour and lunch-hour thin trading. 12:45 is a common ORB reference point in Indian market literature.

### ORB-ADR-004: orb_monitor uses IntervalTrigger anchored at 9:25

**Decision:** `IntervalTrigger(minutes=5, start_date=today@09:25)` instead of a CronTrigger listing each minute.

**Rationale:** This produces ticks at 09:25, 09:30, 09:35, … 15:30 — exactly aligned with 5-min candle close times. A CronTrigger with `minute="25,30,35,..."` would be verbose and error-prone. The IntervalTrigger is self-documenting and handled identically to the existing `alert_monitor` job.

### ORB-ADR-005: Both Long and Short signals are fully independent

**Decision:** A Long signal firing does NOT prevent a Short signal from firing later on the same day, and vice versa.

**Rationale:** The user confirmed both can fire. In practice, if a Long breakout fails and reverses strongly, the Short signal captures the failure. Suppressing one direction after the other fires would miss real trading setups.
