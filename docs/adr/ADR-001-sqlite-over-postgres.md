# ADR-001 — SQLite over PostgreSQL

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch runs on a single machine with a single user. It needs a persistent store for ~500 stocks, daily scan signals, alerts, alert history, and a candle cache. It has no web-facing traffic and no concurrent writers beyond the background scheduler and the FastAPI request handler.

## Decision

Use SQLite as the database engine, accessed via SQLAlchemy 2.x ORM.

## Rationale

- **Zero ops**: no install, no service to manage, no connection pooling to configure
- **Single-user workload**: SQLite's single-writer model is a feature, not a limitation here — the scheduler and API share the same process with session-per-request isolation
- **WAL mode**: `PRAGMA journal_mode=WAL` allows concurrent reads while a write is in progress, sufficient for the candle cache write + API read pattern
- **Sufficient scale**: candle cache for 500 stocks × 252 days × 5 years ≈ 630,000 rows — SQLite handles millions of rows comfortably

## Consequences

- Cannot easily scale to multi-user or multi-node deployment without migrating to PostgreSQL
- SQLite does not enforce strict foreign key constraints by default — must `PRAGMA foreign_keys=ON` per connection
- Alembic migration tool fully supports SQLite, but some ALTER TABLE operations require table reconstruction

## Alternatives Considered

- **PostgreSQL**: rejected — requires a running server, adds operational complexity with no benefit for a single-user desktop tool
- **TinyDB / JSON files**: rejected — no SQL query capability, no Alembic migrations
