# T07 — CandleCacheService

| Field | Value |
|-------|-------|
| Phase | 1 |
| Depends on | T02 |
| Unlocks | T08 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Implement the local SQLite candle cache. Stores daily OHLC rows, detects which date ranges are missing for a given stock, and prevents caching today's partial candle during market hours.

## Files to Create

- `backend/app/services/candle_cache.py`

## Steps

### `backend/app/services/candle_cache.py`

```python
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.models.candle import CandleCache

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


def _market_closed_today() -> bool:
    """Return True if it's past 15:30 IST today (safe to cache today's candle)."""
    now = datetime.now(IST)
    close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE,
                        second=0, microsecond=0)
    return now >= close


def store_candles(db: Session, security_id: str, candles: list[dict]) -> int:
    """
    Upsert a list of candle dicts into candle_cache.
    Each dict: {date: "YYYY-MM-DD", open, high, low, close, volume}
    Skips today's candle if market is still open.
    Returns number of rows stored.
    """
    today = datetime.now(IST).strftime("%Y-%m-%d")
    stored = 0

    for c in candles:
        trade_date = c["date"]
        if trade_date == today and not _market_closed_today():
            continue   # don't cache partial intraday candle

        existing = (db.query(CandleCache)
                    .filter_by(security_id=security_id, trade_date=trade_date)
                    .first())
        if existing:
            continue   # historical data is immutable — no need to update

        db.add(CandleCache(
            security_id=security_id,
            trade_date=trade_date,
            open=c["open"],
            high=c["high"],
            low=c["low"],
            close=c["close"],
            volume=c["volume"],
            fetched_at=datetime.now(IST).isoformat(),
        ))
        stored += 1

    db.commit()
    return stored


def get_cached_candles(
    db: Session,
    security_id: str,
    from_date: str,   # YYYY-MM-DD
    to_date: str,     # YYYY-MM-DD
) -> list[dict]:
    """Return cached candles for the given security and date range."""
    rows = (db.query(CandleCache)
            .filter(
                CandleCache.security_id == security_id,
                CandleCache.trade_date >= from_date,
                CandleCache.trade_date <= to_date,
            )
            .order_by(CandleCache.trade_date)
            .all())
    return [
        {"date": r.trade_date, "open": r.open, "high": r.high,
         "low": r.low, "close": r.close, "volume": r.volume}
        for r in rows
    ]


def find_missing_ranges(
    db: Session,
    security_id: str,
    from_date: str,
    to_date: str,
) -> list[tuple[str, str]]:
    """
    Compare cached dates against the expected date range.
    Returns list of (range_start, range_end) tuples for contiguous missing gaps.

    Strategy: generate all weekday dates in [from_date, to_date],
    compare against cached set, group contiguous missing weekdays into ranges.
    Note: Dhan simply returns no data for market holidays within weekdays —
    the cache will naturally be sparse on those, which is fine.
    """
    cached_rows = (db.query(CandleCache.trade_date)
                   .filter(
                       CandleCache.security_id == security_id,
                       CandleCache.trade_date >= from_date,
                       CandleCache.trade_date <= to_date,
                   ).all())
    cached_dates = {r.trade_date for r in cached_rows}

    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)

    missing_gaps = []
    gap_start = None

    current = start
    while current <= end:
        ds = current.strftime("%Y-%m-%d")
        if current.weekday() < 5 and ds not in cached_dates:  # weekday not cached
            if gap_start is None:
                gap_start = ds
        else:
            if gap_start is not None:
                gap_end = (current - timedelta(days=1)).strftime("%Y-%m-%d")
                missing_gaps.append((gap_start, gap_end))
                gap_start = None
        current += timedelta(days=1)

    if gap_start is not None:
        missing_gaps.append((gap_start, end.strftime("%Y-%m-%d")))

    return missing_gaps
```

## Done When
- `store_candles(db, "2885", candles)` correctly upserts rows; re-running does not duplicate
- `get_cached_candles(db, "2885", "2024-01-01", "2024-01-15")` returns only rows in the range, sorted by date
- `find_missing_ranges(db, "2885", "2024-01-01", "2024-01-15")` returns correct gap tuples when some dates are missing
- Today's candle is NOT stored if called before 15:30 IST; IS stored if called after 15:30 IST
