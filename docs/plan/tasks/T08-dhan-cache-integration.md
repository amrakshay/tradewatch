# T08 — DhanService + Cache Integration

| Field | Value |
|-------|-------|
| Phase | 1 |
| Depends on | T06, T07 |
| Unlocks | T09, T10, T12, T13 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Add the cache-first `get_daily_ohlc()` method to DhanService that uses CandleCacheService to serve cached data and only calls the Dhan API for missing date ranges.

## Files to Modify

- `backend/app/services/dhan_service.py` (add `get_daily_ohlc()` method)

## Steps

Add the following method to the `DhanService` class in `dhan_service.py`:

```python
async def get_daily_ohlc(
    self,
    security_id: str,
    from_date: str,         # YYYY-MM-DD
    to_date: str,           # YYYY-MM-DD
    db: Session = None,
    exchange_segment: str = "NSE_EQ",
) -> list[dict]:
    """
    Cache-first daily OHLC fetch.
    1. Get cached candles for the range.
    2. Find missing date gaps.
    3. Fetch only missing ranges from Dhan API.
    4. Store newly fetched candles in cache.
    5. Merge and return sorted list.
    """
    if db is None:
        # Fallback: raw fetch without caching
        return await self.get_daily_ohlc_raw(security_id, from_date, to_date, exchange_segment)

    from app.services.candle_cache import (
        get_cached_candles, find_missing_ranges, store_candles
    )

    # Step 1: what we already have
    cached = get_cached_candles(db, security_id, from_date, to_date)

    # Step 2: find gaps
    missing_ranges = find_missing_ranges(db, security_id, from_date, to_date)

    if not missing_ranges:
        logger.debug(f"Cache hit: {security_id} {from_date}→{to_date}")
        return cached

    # Step 3+4: fetch each missing range and store
    new_candles = []
    for gap_start, gap_end in missing_ranges:
        logger.debug(f"Cache miss: fetching {security_id} {gap_start}→{gap_end}")
        fetched = await self.get_daily_ohlc_raw(
            security_id, gap_start, gap_end, exchange_segment
        )
        store_candles(db, security_id, fetched)
        new_candles.extend(fetched)

    # Step 5: merge cached + newly fetched, deduplicate by date, sort
    all_candles = {c["date"]: c for c in cached}
    all_candles.update({c["date"]: c for c in new_candles})
    return sorted(all_candles.values(), key=lambda c: c["date"])
```

## Usage Pattern

All callers (ScannerService, BacktestService) should use `get_daily_ohlc()` not `get_daily_ohlc_raw()`:

```python
candles = await dhan_service.get_daily_ohlc(
    security_id="2885",
    from_date="2024-01-01",
    to_date="2024-01-15",
    db=db,
)
```

## Done When
- First call fetches from Dhan API and stores in cache
- Second call for same stock/range returns from cache with 0 API calls (verify via log output)
- Partial cache hit (some dates cached, some not) only fetches the missing ranges
- Result is always sorted by date and contains no duplicate dates
