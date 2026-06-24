# ADR-007 — Local SQLite Candle Cache

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

Scanning 500 stocks daily via Dhan's historical data API requires ~500 API calls per scan. Each backtest for a stock requires additional API calls. The Dhan API has a 100,000/day limit and rate limit of 5 req/sec. Without caching, repeated backtests and re-scans would exhaust the daily quota and be slow.

## Decision

Cache daily OHLC candles in the `candle_cache` SQLite table. All callers use `DhanService.get_daily_ohlc()` (cache-first) rather than `get_daily_ohlc_raw()` (direct API).

## Cache Logic

1. Check what's cached for `(security_id, from_date, to_date)`
2. Find missing date gaps (weekday dates not in cache)
3. Fetch only missing ranges from Dhan API
4. Store newly fetched candles
5. Merge and return

**Today's candle guard**: if `now < 15:30 IST`, today's candle is NOT cached (it's the incomplete intraday candle, not the final close). After 15:30, it's safe to cache. The scanner runs at 15:45 by default, so this guard is automatically lifted before the scan.

## Consequences

- First run fetches all data from Dhan API; subsequent runs for the same range are instant
- Cache is permanent (historical data is immutable); no TTL/expiry needed
- For 500 stocks × 252 days/year × 5 years: ~630,000 rows — well within SQLite limits
- `candle_cache` table has `UNIQUE(security_id, trade_date)` constraint — upsert safety

## Alternatives Considered

- **No cache (always fetch live)**: rejected — slow (100s per scan) and burns daily API quota
- **File-based cache (CSV/pickle)**: rejected — harder to query for gap detection; no SQL
- **Redis**: rejected — operational overhead for a desktop tool
