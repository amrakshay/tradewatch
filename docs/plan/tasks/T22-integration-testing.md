# T22 — Integration Testing & Launch Checklist

| Field | Value |
|-------|-------|
| Phase | 4 |
| Depends on | T14, T17, T18, T19, T20, T21 |
| Unlocks | — (final task) |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
End-to-end verification of all system flows: startup sequence, scheduler jobs, scan-to-signal-to-alert pipeline, Telegram notification, backtest, edge cases (market holidays, empty configs, bad credentials). Also covers launch checklist items before first real-money use.

## Test Flows

### 1. First-Run Setup

```
1. alembic upgrade head        → tradewatch.db created with 6 tables + alembic_version
2. python scripts/seed_db.py   → app_config row seeded (id=1)
3. uvicorn app.main:app        → FastAPI starts, scheduler starts, 4 jobs registered
4. GET /api/scheduler/status   → 4 jobs listed with next_run values
5. GET /api/config             → config returned with empty (masked) token fields
```

### 2. Configuration Flow

```
1. PUT /api/config { dhan_client_id, dhan_access_token }
   → stored encrypted; masked in next GET
2. PUT /api/config { dhan_access_token: "<masked_value>" }
   → NOT overwritten (masked value guard triggers)
3. POST /api/config/test-dhan
   → {valid: true, expires_at: "..."} if credentials correct
4. PUT /api/config { telegram_bot_token, telegram_chat_id }
5. POST /api/config/test-telegram
   → test message arrives in Telegram chat
```

### 3. Stock Universe

```
1. POST /api/stocks/sync-nifty500
   → {matched: ~480, unmatched: ~20}
2. GET /api/stocks
   → list of ~480 stocks with correct security_ids
3. PATCH /api/stocks/{id}?is_active=false
   → stock excluded from next scan
4. POST /api/stocks { symbol, security_id, name }   (custom stock)
   → appears in GET /api/stocks with universe_tag=CUSTOM
```

### 4. Scanner Flow

```
1. POST /api/scanner/run (market day, 15:45+)
   → {scan_date, total_scanned: ~480, qualified: N, signals: [...]}
2. GET /api/signals?date=YYYY-MM-DD
   → same N signals, sorted by return_pct desc
3. GET /api/signals/dates
   → [today's date, ...] (most recent first)
4. POST /api/scanner/run (same day)
   → same date returned; no duplicate signals in DB
   → (verify via sqlite3: SELECT COUNT(*) FROM scan_signals WHERE scan_date=?)
```

### 5. Alert Flow

```
1. POST /api/alerts
   { symbol, security_id, signal_date, alert_price: <close * 0.99>, valid_days: 7 }
   → status=active, expires_at set correctly
2. GET /api/alerts?status=active  → alert appears
3. GET /api/alerts/{id}/history   → [{"event_type": "created", ...}]
4. POST /api/alerts/check          → (manual trigger, bypass_window_guard=true)
   → if LTP <= alert_price: status=triggered, Telegram message sent
   → else: alert remains active
5. PATCH /api/alerts/{id}
   { alert_price: <new>, valid_days: 14 }
   → updated; history has "updated" event
6. DELETE /api/alerts/{id}
   → removed; history has "deleted" event (check DB before delete clears it)
7. Create alert with expires_at in the past → POST /api/alerts/check → status=expired
```

### 6. Backtest Flow

```
1. POST /api/backtest
   { symbol: "RELIANCE", security_id: "2885",
     from_date: "2023-01-01", to_date: "2023-12-31",
     pct_threshold: 10.0, num_days: 4 }
   → results list with dates, close/start prices, return_pct
2. Run same backtest again
   → identical results (idempotent); check logs: "Cache hit: 2885 ..."
3. Verify hit rate is sensible (not 0%, not 100%)
```

### 7. Scheduler Edge Cases

```
1. PUT /api/config { scan_time: "16:00" }
   → GET /api/scheduler/status: daily_scan.next_run updated to 16:00
2. PUT /api/config { alert_check_interval_mins: 15 }
   → GET /api/scheduler/status: alert_monitor interval updated
3. Restart backend (uvicorn restart)
   → scheduler re-reads config, registers jobs with correct times
```

### 8. Candle Cache Verification

```
1. Run scanner (populates cache for ~480 stocks)
2. Check DB: SELECT COUNT(*) FROM candle_cache; → should be > 0
3. Run backtest for RELIANCE, observe logs: "Cache hit" messages on second call
4. Run before 15:30 IST (if testing during market hours):
   → today's candle is NOT cached (check: SELECT MAX(trade_date) FROM candle_cache)
```

## Edge Cases to Verify

| Scenario | Expected Behavior |
|----------|------------------|
| Dhan API down during scan | Error logged; scan_signals not written for that run; no crash |
| Market holiday (scanner fires, Dhan returns empty) | No signals written; no error; scheduler proceeds |
| Bad Dhan credentials | `test-dhan` returns `{valid: false}`; token_status = "invalid" |
| Telegram bot token invalid | `test-telegram` returns `{sent: false}`; no crash |
| Scanner run before any stocks synced | Returns `{total_scanned: 0, qualified: 0}` |
| Alert check with no active alerts | Logs "no active alerts"; exits early; no API call |
| DB write during concurrent scan | SQLite WAL mode + session-per-request prevents corruption |

## Pre-Launch Checklist

### Security
- [ ] `backend/.secret_key` is in `.gitignore` and NOT committed
- [ ] `tradewatch.db` is in `.gitignore` and NOT committed
- [ ] `.env` is in `.gitignore` and NOT committed
- [ ] Dhan access token stored encrypted (verify: `sqlite3 tradewatch.db "SELECT dhan_access_token FROM app_config"` — should be a Fernet ciphertext, not plaintext)

### Configuration
- [ ] Dhan Client ID and Access Token set via Settings page
- [ ] `POST /api/config/test-dhan` returns `{valid: true}`
- [ ] Telegram Bot Token and Chat ID configured
- [ ] `POST /api/config/test-telegram` delivers message
- [ ] Nifty 500 synced (≥ 400 stocks with `is_active=1`)

### Scheduler
- [ ] `GET /api/scheduler/status` shows 4 jobs
- [ ] `daily_scan` next_run is set to next trading day at 15:45 IST
- [ ] `token_renew` next_run is set to tomorrow at 09:00 IST

### Operations
- [ ] `start.sh` brings up both backend and frontend cleanly
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] Alembic migration applied: `alembic current` shows head revision
- [ ] First manual scan run via `POST /api/scanner/run` succeeds

## Alembic Migration Workflow for Future Changes

When adding a new column or table after initial deployment:

```bash
# 1. Edit the SQLAlchemy model
# 2. Generate migration
alembic revision --autogenerate -m "add_column_xyz"
# 3. Review the generated migration file
# 4. Apply
alembic upgrade head
# 5. Verify
alembic current
```

Never edit a migration that has already been applied in production. Always generate a new one.
