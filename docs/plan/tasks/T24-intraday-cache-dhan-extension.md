# T24 — IntradayCacheService + DhanService Intraday Extension

**Phase:** ORB Phase 1
**Depends on:** T07 (CandleCacheService pattern), T08 (DhanService cache integration), T23
**Blocks:** T25, T28

---

## Goal

Add 5-min intraday OHLC fetching to `DhanService` with a local SQLite cache (same cache-first pattern as daily candles). Create `IntradayCacheService` for the `intraday_candle_cache` table.

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `backend/app/services/intraday_cache.py` |
| Modify | `backend/app/services/dhan_service.py` |
| Create | `backend/app/schemas/orb.py` (IntradayCandle dataclass) |

---

## Implementation

### 1. `IntradayCandle` dataclass (in `schemas/orb.py` or a shared models file)

```python
from dataclasses import dataclass
from datetime import date as Date

@dataclass
class IntradayCandle:
    trade_date:  str   # YYYY-MM-DD
    candle_time: str   # "HH:MM" IST (candle open time)
    open:        float
    high:        float
    low:         float
    close:       float
    volume:      int
```

### 2. `backend/app/services/intraday_cache.py`

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.models.orb import IntradayCandleCache
from app.schemas.orb import IntradayCandle

IST = ZoneInfo("Asia/Kolkata")

class IntradayCacheService:

    def __init__(self, db: Session):
        self.db = db

    def get_cached_candles(self, security_id: str, trade_date: date,
                           interval_mins: int = 5) -> list[IntradayCandle]:
        rows = (self.db.query(IntradayCandleCache)
                .filter_by(security_id=security_id,
                           trade_date=str(trade_date),
                           interval_mins=interval_mins)
                .order_by(IntradayCandleCache.candle_time)
                .all())
        return [IntradayCandle(
            trade_date=r.trade_date, candle_time=r.candle_time,
            open=r.open, high=r.high, low=r.low,
            close=r.close, volume=r.volume
        ) for r in rows]

    def store_candles(self, security_id: str, trade_date: date,
                      candles: list[IntradayCandle], interval_mins: int = 5):
        now_ist = datetime.now(IST).isoformat()
        for c in candles:
            existing = (self.db.query(IntradayCandleCache)
                        .filter_by(security_id=security_id,
                                   trade_date=c.trade_date,
                                   candle_time=c.candle_time,
                                   interval_mins=interval_mins)
                        .first())
            if not existing:
                self.db.add(IntradayCandleCache(
                    security_id=security_id,
                    trade_date=c.trade_date,
                    candle_time=c.candle_time,
                    interval_mins=interval_mins,
                    open=c.open, high=c.high, low=c.low,
                    close=c.close, volume=c.volume,
                    fetched_at=now_ist
                ))
        self.db.commit()

    def is_date_cached(self, security_id: str, trade_date: date,
                       interval_mins: int = 5) -> bool:
        """Returns True if we have at least one candle row for this date."""
        return self.db.query(IntradayCandleCache).filter_by(
            security_id=security_id,
            trade_date=str(trade_date),
            interval_mins=interval_mins
        ).first() is not None
```

### 3. `DhanService.get_intraday_5min()` — add to existing `dhan_service.py`

```python
async def get_intraday_5min(
    self,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: date,
    to_date: date,
    db: Session
) -> list[IntradayCandle]:
    """
    Returns 5-min candles for the given date range, cache-first.
    Fetches from Dhan only for dates not in cache.
    Today's candles are NOT cached (live data needed for ORB monitoring).
    """
    cache = IntradayCacheService(db)
    all_candles = []
    today = datetime.now(IST).date()

    current = from_date
    while current <= to_date:
        # Never cache today's data during market hours
        if current == today:
            candles = await self._fetch_intraday_from_dhan(
                security_id, exchange_segment, instrument_type, current, current
            )
        elif cache.is_date_cached(security_id, current):
            candles = cache.get_cached_candles(security_id, current)
        else:
            candles = await self._fetch_intraday_from_dhan(
                security_id, exchange_segment, instrument_type, current, current
            )
            if candles:  # only cache past dates with data
                cache.store_candles(security_id, current, candles)

        all_candles.extend(candles)
        current += timedelta(days=1)

    return sorted(all_candles, key=lambda c: (c.trade_date, c.candle_time))

async def _fetch_intraday_from_dhan(
    self,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: date,
    to_date: date
) -> list[IntradayCandle]:
    """
    Calls POST /v2/charts/intraday with interval=5.
    Converts epoch timestamps to IST "HH:MM" candle_time strings.
    """
    try:
        response = self.dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            interval=5,
            from_date=f"{from_date} 09:15:00",
            to_date=f"{to_date} 15:30:00"
        )
        # Parse the parallel arrays response
        timestamps = response.get("timestamp", [])
        opens   = response.get("open", [])
        highs   = response.get("high", [])
        lows    = response.get("low", [])
        closes  = response.get("close", [])
        volumes = response.get("volume", [])

        candles = []
        for i, ts in enumerate(timestamps):
            dt = datetime.fromtimestamp(ts, tz=IST)
            candles.append(IntradayCandle(
                trade_date=str(dt.date()),
                candle_time=dt.strftime("%H:%M"),
                open=opens[i], high=highs[i], low=lows[i],
                close=closes[i], volume=volumes[i]
            ))
        return candles

    except Exception as e:
        logger.error(f"Dhan intraday fetch failed for {security_id}: {e}")
        return []
```

---

## Notes

- Dhan returns candle timestamps as Unix epoch; convert using `datetime.fromtimestamp(ts, tz=IST)` to get IST time
- `intraday_minute_data()` is the dhanhq SDK method name for the `/charts/intraday` endpoint — verify against installed SDK version
- Rate limit: same 5 req/sec as historical data API; for 2–5 ORB instruments, calls are minimal

---

## Done When

- [ ] `IntradayCacheService` can store and retrieve 5-min candles from `intraday_candle_cache`
- [ ] `DhanService.get_intraday_5min()` returns candles for a given date range
- [ ] Past dates are served from cache on second call (no Dhan API call)
- [ ] Today's date always fetches live from Dhan
- [ ] Manual test: fetch NIFTY 5-min data for a past date, confirm cache hit on re-fetch
