# TradeWatch — Implementation Plan

> This is the single source of truth for build sequence, task ownership, and dependencies.
> Each task has a dedicated file in `docs/plan/tasks/`. ADRs live in `docs/adr/`.

---

## Quick Reference

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](../../ARCHITECTURE.md) | Full system design, schema, API spec |
| `docs/plan/tasks/T##-*.md` | Per-task implementation spec |
| `docs/adr/ADR-###-*.md` | Architecture decision records |

---

## Task Index

| ID | Task | Phase | Depends On | Est. |
|----|------|-------|-----------|------|
| [T01](tasks/T01-project-structure.md) | Project structure & tooling setup | 0 | — | 0.5d |
| [T02](tasks/T02-database-models.md) | Database models & schema | 0 | T01 | 0.5d |
| [T03](tasks/T03-encryption-service.md) | EncryptionService | 0 | T01 | 0.5d |
| [T04](tasks/T04-config-service.md) | ConfigService | 0 | T02, T03 | 0.5d |
| [T05](tasks/T05-token-service.md) | TokenService | 1 | T04 | 1d |
| [T06](tasks/T06-dhan-service.md) | DhanService (base) | 1 | T04 | 1d |
| [T07](tasks/T07-candle-cache.md) | CandleCacheService | 1 | T02 | 0.5d |
| [T08](tasks/T08-dhan-cache-integration.md) | DhanService + cache integration | 1 | T06, T07 | 0.5d |
| [T09](tasks/T09-stock-universe.md) | Stock universe seeding + API | 1 | T06 | 1d |
| [T10](tasks/T10-scanner-service.md) | ScannerService + API | 2 | T08, T09 | 1.5d |
| [T11](tasks/T11-telegram-service.md) | TelegramService | 1 | T04 | 0.5d |
| [T12](tasks/T12-alert-service.md) | AlertService + API | 2 | T08, T11 | 1.5d |
| [T13](tasks/T13-backtest-service.md) | BacktestService + API | 2 | T08 | 1d |
| [T14](tasks/T14-scheduler.md) | APScheduler integration | 2 | T05, T10, T12 | 1d |
| [T15](tasks/T15-config-api.md) | Config & Health API | 2 | T04, T05, T11 | 0.5d |
| [T16](tasks/T16-react-scaffold.md) | React frontend scaffold | 3 | T01 | 1d |
| [T17](tasks/T17-settings-page.md) | Settings page | 3 | T16, T15, T09 | 1d |
| [T18](tasks/T18-signals-page.md) | Signals page | 3 | T16, T10, T12 | 1d |
| [T19](tasks/T19-alerts-page.md) | Alerts page | 3 | T16, T12 | 1d |
| [T20](tasks/T20-backtest-page.md) | Backtest page | 3 | T16, T13 | 1d |
| [T21](tasks/T21-dashboard-page.md) | Dashboard page | 3 | T16, T10, T12, T15 | 0.5d |
| [T22](tasks/T22-integration-testing.md) | Integration testing & deployment | 4 | All | 1d |

**Total estimated: ~17 days solo**

---

## Dependency Graph

```
T01 ──┬── T02 ──┬── T04 ──┬── T05 ──────────────────────────── T14
      │         │         ├── T06 ──┬── T08 ──┬── T09 ── T10 ──┤
      │         │         │         │         │                 │
      │         └── T03 ──┘         │         ├── T10 ──────────┤
      │                             │         ├── T12 ──────────┤
      │                    T07 ─────┘         └── T13           │
      │                    (needs T02)                          │
      │                                                         │
      │         T04 ── T11 ─────────────────────── T12 ─────────┤
      │                                                         │
      └── T16 ──┬── T17 (needs T15, T09)                       │
                ├── T18 (needs T10, T12)                        │
                ├── T19 (needs T12)                             │
                ├── T20 (needs T13)                             │
                └── T21 (needs T10, T12, T15)                  │
                                                                │
All ─────────────────────────────────────────────────────── T22
```

---

## Phase Breakdown

### Phase 0 — Foundation (Days 1–2)

Establish the base everything else builds on. No business logic yet.

| Task | What it delivers |
|------|----------------|
| T01 | Folder structure, venv, Vite scaffold, start.sh skeleton |
| T02 | All SQLAlchemy models, init_db.py, database.py |
| T03 | EncryptionService with Fernet key management |
| T04 | ConfigService: read/write app_config, side-effect dispatch |

**Sequence:** T01 → T02 + T03 in parallel → T04

**Milestone:** `python init_db.py` creates a clean `tradewatch.db` with all tables and default config row.

---

### Phase 1 — Core Services (Days 3–7)

Build every service that touches external systems (Dhan, Telegram) and internal data.

| Task | What it delivers |
|------|----------------|
| T05 | TokenService: validity check, daily renew, expiry alert |
| T06 | DhanService base: SDK init, OHLC fetch, LTP batch, instrument CSV |
| T07 | CandleCacheService: SQLite read/write, gap detection |
| T08 | DhanService cache-first: wire T06 + T07 |
| T09 | Stock universe: Nifty 500 seed, stocks CRUD API |
| T11 | TelegramService: send alert, send test (can run alongside T05–T07) |

**Sequence:** T04 → T05 + T06 + T11 (parallel) → T07 (parallel) → T08 → T09

**Milestone:** `python -c "from app.services.dhan_service import DhanService; ..."` fetches OHLC for RELIANCE, caches it, returns from cache on second call. Telegram test message delivered.

---

### Phase 2 — Business Logic + API (Days 8–12)

Scanner, alerts, backtest, scheduler — the complete backend.

| Task | What it delivers |
|------|----------------|
| T10 | ScannerService + all signal endpoints |
| T11 | TelegramService (if not done in Phase 1) |
| T12 | AlertService + all alert endpoints |
| T13 | BacktestService + POST /backtest |
| T14 | APScheduler: all 4 jobs wired, startup token check |
| T15 | Config + Health API endpoints |

**Sequence:** T08 + T09 done → T10 + T12 + T13 (parallel) → T14 + T15

**Milestone:** `uvicorn app.main:app` starts cleanly. Manual `POST /scanner/run` returns signals. `POST /alerts` creates alert. `POST /backtest` returns qualifying dates.

---

### Phase 3 — Frontend (Days 13–17)

React UI, page by page.

| Task | What it delivers |
|------|----------------|
| T16 | Vite + React + Tailwind + shadcn/ui + sidebar layout |
| T17 | Settings page (config, tokens, stock universe) |
| T18 | Signals page (date picker, signal table, set alert modal) |
| T19 | Alerts page (tabs, history panel) |
| T20 | Backtest page (form + results + chart) |
| T21 | Dashboard page (stat cards, recent activity) |

**Sequence:** T16 → T17 → T18 → T19 → T20 → T21

> **Note:** T16 can start in parallel with Phase 1/2 backend work if splitting work. Frontend pages can be built against mock data before backend is ready.

**Milestone:** Full UI running at `localhost:5173`, all pages functional end-to-end with live backend.

---

### Phase 4 — Integration & Deployment (Day 17–18)

| Task | What it delivers |
|------|----------------|
| T22 | Smoke tests, start.sh, edge case fixes |

**Milestone:** `./start.sh` launches both processes. Scanner fires at 15:45, alert monitor checks every 30 min, Telegram notification delivered when alert triggers.

---

## Parallelism Notes (if splitting work)

Even solo, knowing what's independent helps decide what to context-switch to when blocked:

| Can run in parallel |
|---------------------|
| T02 and T03 |
| T05, T06, T07, T11 (all need T04, T02) |
| T10, T12, T13 (all need T08) |
| T16 and any Phase 2 backend task |
| T17, T18, T19, T20, T21 (all need T16) |

---

## ADR Index

All architecture decisions are documented in `docs/adr/`.

| File | Decision |
|------|---------|
| [ADR-001](../adr/ADR-001-monolithic-backend.md) | Monolithic backend (single FastAPI process) |
| [ADR-002](../adr/ADR-002-sqlite.md) | SQLite as primary database |
| [ADR-003](../adr/ADR-003-apscheduler.md) | APScheduler embedded in FastAPI |
| [ADR-004](../adr/ADR-004-ltp-polling.md) | LTP REST polling vs WebSocket |
| [ADR-005](../adr/ADR-005-react-vite.md) | React + Vite for frontend |
| [ADR-006](../adr/ADR-006-credential-encryption.md) | Fernet encryption for credentials |
| [ADR-007](../adr/ADR-007-candle-cache.md) | SQLite candle cache |
| [ADR-008](../adr/ADR-008-scan-time-1545.md) | Default scan time 15:45 IST |
| [ADR-009](../adr/ADR-009-close-time-check.md) | Dedicated 15:30 alert check job |
| [ADR-010](../adr/ADR-010-ist-timestamps.md) | IST timestamps throughout |
| [ADR-011](../adr/ADR-011-backtest-buffer.md) | Fixed 14-day backtest lookback buffer |
| [ADR-012](../adr/ADR-012-telegram-html.md) | Telegram HTML parse mode |
| [ADR-013](../adr/ADR-013-token-renewal.md) | Daily token renewal at 09:00 IST |
