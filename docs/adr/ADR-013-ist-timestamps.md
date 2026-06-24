# ADR-013 — All Timestamps Written in IST via Python datetime

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch runs in India and all business logic (market hours, scan times, alert windows, candle dates) is expressed in IST (UTC+5:30). SQLite stores text dates/times as strings. There are two ways timestamps can be written:

1. **SQLite `datetime('now')`**: returns UTC in the database's built-in function. On a machine with IST timezone, `datetime('now')` is correct UTC but **displays as UTC, not IST** — a consistent source of confusion and subtle bugs when comparing dates.
2. **Python `datetime.now(IST).isoformat()`**: always writes the current local time with the IST timezone offset (`+05:30`).

## Decision

All timestamp fields written to the database use Python's `datetime.now(IST).isoformat()`. SQLite's `datetime('now')` and `func.now()` are never used for application timestamps.

```python
from zoneinfo import ZoneInfo
from datetime import datetime

IST = ZoneInfo("Asia/Kolkata")

# Always:
created_at = datetime.now(IST).isoformat()  # "2024-01-15T15:45:03.421000+05:30"

# Never:
# created_at = func.now()  # returns UTC
```

## Rationale

- **Consistency**: all timestamps in DB are in IST; no mental UTC-to-IST conversion when reading records
- **Correctness**: `scan_date`, `created_at`, `triggered_at`, `expires_at` all align with the user's local date
- **Explicit timezone**: `isoformat()` on a timezone-aware datetime includes the `+05:30` offset — unambiguous even if the system timezone changes
- **Candle cache**: `trade_date` is formatted via `datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d")` — always the IST date of the trading session

## Consequences

- Timestamps in the DB look like `2024-01-15T15:45:03.421000+05:30` — slightly longer but unambiguous
- Date comparisons in queries use string comparison on ISO format — works correctly since ISO dates sort lexicographically
- If the machine timezone is changed, `datetime.now(IST)` is unaffected (IST is explicit)

## Alternatives Rejected

- **UTC everywhere**: common best practice for multi-timezone apps; rejected here because TradeWatch is India-only; UTC adds confusion without benefit
- **SQLite `datetime('now')`**: rejected — writes UTC silently; comparing against Python-generated IST dates produces subtle off-by-5:30h bugs
