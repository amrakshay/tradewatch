# T13 — BacktestService + API

| Field | Value |
|-------|-------|
| Phase | 3 |
| Depends on | T08 |
| Unlocks | T20 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the backtest engine: given a stock, date range, and scan parameters, return every trading day in the range where the stock would have appeared in the daily scanner.

## Files to Create

- `backend/app/services/backtest_service.py`
- `backend/app/routers/backtest.py`
- `backend/app/schemas/backtest.py`

## Algorithm

```
Input:
  symbol, security_id
  from_date, to_date
  pct_threshold, num_days

Step 1: fetch_from = from_date - 14 calendar days (fixed buffer)
Step 2: candles = get_daily_ohlc(security_id, fetch_from, to_date)
Step 3: start_idx = first candle index where date >= from_date
Step 4: for i in range(start_idx, len(candles)):
            if i < num_days: continue
            today  = candles[i]
            n_ago  = candles[i - num_days]
            ret    = (today.close - n_ago.close) / n_ago.close * 100
            if ret >= pct_threshold:
                append result
```

The 14-day calendar buffer ensures `candles[i - num_days]` is always valid when `i` points to a date within the requested range, even with holidays.

## Steps

### 1. `backend/app/schemas/backtest.py`

```python
from pydantic import BaseModel

class BacktestRequest(BaseModel):
    symbol: str
    security_id: str
    from_date: str          # YYYY-MM-DD
    to_date: str            # YYYY-MM-DD
    pct_threshold: float = 10.0
    num_days: int = 4

class BacktestResult(BaseModel):
    date: str
    close_price: float
    start_price: float
    return_pct: float

class BacktestResponse(BaseModel):
    symbol: str
    security_id: str
    from_date: str
    to_date: str
    pct_threshold: float
    num_days: int
    total_trading_days: int
    qualifying_days: int
    results: list[BacktestResult]
```

### 2. `backend/app/services/backtest_service.py`

```python
import logging
from zoneinfo import ZoneInfo
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.services.dhan_service import get_dhan_service

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

BACKTEST_BUFFER_DAYS = 14   # calendar days prepended before from_date


async def run_backtest(
    db: Session,
    symbol: str,
    security_id: str,
    from_date: str,      # YYYY-MM-DD
    to_date: str,        # YYYY-MM-DD
    pct_threshold: float,
    num_days: int,
    exchange_segment: str = "NSE_EQ",
) -> dict:
    """
    Run backtest for a single stock over the given date range.
    Returns qualifying days where return_pct >= pct_threshold.
    """
    # Fetch with buffer
    fetch_from = (date.fromisoformat(from_date) - timedelta(days=BACKTEST_BUFFER_DAYS)).isoformat()

    dhan = get_dhan_service(db)
    candles = await dhan.get_daily_ohlc(
        security_id=security_id,
        from_date=fetch_from,
        to_date=to_date,
        db=db,
        exchange_segment=exchange_segment,
    )

    # Only candles within the requested [from_date, to_date] range count toward results
    # but we need the buffer candles for lookback calculations
    results = []
    trading_days_in_range = 0

    for i in range(len(candles)):
        cdate = candles[i]["date"]
        if cdate < from_date:
            continue   # buffer candle — used for lookback only
        if cdate > to_date:
            break

        trading_days_in_range += 1

        if i < num_days:
            continue   # not enough lookback

        today_close = candles[i]["close"]
        start_close = candles[i - num_days]["close"]

        if start_close == 0:
            continue

        ret_pct = (today_close - start_close) / start_close * 100

        if ret_pct >= pct_threshold:
            results.append({
                "date": cdate,
                "close_price": today_close,
                "start_price": start_close,
                "return_pct": round(ret_pct, 2),
            })

    return {
        "symbol": symbol,
        "security_id": security_id,
        "from_date": from_date,
        "to_date": to_date,
        "pct_threshold": pct_threshold,
        "num_days": num_days,
        "total_trading_days": trading_days_in_range,
        "qualifying_days": len(results),
        "results": results,
    }
```

### 3. `backend/app/routers/backtest.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import backtest_service
from app.schemas.backtest import BacktestRequest, BacktestResponse

router = APIRouter(prefix="/api", tags=["backtest"])


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    return await backtest_service.run_backtest(
        db=db,
        symbol=body.symbol,
        security_id=body.security_id,
        from_date=body.from_date,
        to_date=body.to_date,
        pct_threshold=body.pct_threshold,
        num_days=body.num_days,
    )
```

### 4. Register router in `main.py`

```python
from app.routers import backtest
app.include_router(backtest.router)
```

## Done When
- `POST /api/backtest` with valid stock + date range returns `{total_trading_days, qualifying_days, results: [...]}`
- Results are sorted by date ascending
- A stock with known strong performance period shows expected qualifying dates
- Running backtest twice for same stock/range returns identical results (idempotent via cache)
- Response for 1-year range on Nifty 500 stock completes within 5 seconds (cache hit after first call)
