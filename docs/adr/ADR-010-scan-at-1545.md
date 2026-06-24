# ADR-010 — Default Scan Time 15:45 IST (not 15:30)

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

The NSE market closes at 15:30 IST. The scanner computes returns using the closing price. If the scan runs exactly at 15:30 or slightly before, Dhan's historical data API may not have finalized the day's closing candle yet — it may return the last traded price or an incomplete candle.

## Decision

Default the scan time to **15:45 IST** (15 minutes after market close). This is configurable via Settings.

## Rationale

- **Data finalization**: Dhan's daily candle API (`historical_daily_data`) typically reflects the official closing price within a few minutes of 15:30, but a 15-minute buffer eliminates any race condition
- **Candle cache boundary**: the `CandleCacheService` guard "don't cache today's candle before 15:30" is already lifted at 15:45, so today's candle is safely cacheable when the scanner runs
- **No meaningful downside**: the 15-minute delay has no trading impact — TradeWatch sets watchlist alerts, not live orders

## Consequences

- Users can change scan time to 15:30 via Settings if they prefer, accepting the risk of occasional incomplete candle data
- The scheduler reads `config.scan_time` on startup and reschedules if changed via config API

## Alternatives Considered

- **15:30 exactly**: rejected — risk of fetching incomplete candle data; scanner result for the day depends on when exactly Dhan finalizes OHLC
- **16:00**: unnecessary delay; 15:45 is sufficient
