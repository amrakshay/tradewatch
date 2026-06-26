# T28 — ORB Backtest Service + API

**Phase:** ORB Phase 2
**Depends on:** T24 (intraday data + cache)
**Blocks:** T30 (frontend backtest page)

---

## Goal

Implement an ORB backtesting engine that replays the signal logic over historical 5-min candle data for any instrument and date range. Results are returned in-memory (not stored to DB).

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `backend/app/services/orb_backtest_service.py` |
| Modify | `backend/app/routers/orb.py` (add POST /orb/backtest) |
| Modify | `backend/app/schemas/orb.py` (request/response schemas) |

---

## Pydantic Schemas (add to `schemas/orb.py`)

```python
class ORBBacktestRequest(BaseModel):
    symbol:                  str
    security_id:             str
    exchange_segment:        str = "IDX_I"
    instrument_type:         str = "INDEX"
    from_date:               str   # YYYY-MM-DD
    to_date:                 str   # YYYY-MM-DD
    body_pct_threshold:      float = 0.6
    volume_ratio_threshold:  float = 1.5

class ORBBacktestSignalDetail(BaseModel):
    breakout_time:          str
    signal_price:           float
    breakout_candle_volume: int
    prev_candle_volume:     int

class ORBBacktestDayResult(BaseModel):
    date:                     str
    orb_high:                 float
    orb_low:                  float
    first_candle_direction:   str
    first_candle_strong:      bool
    first_candle_body_pct:    float
    first_candle_volume_ratio: float
    long_signal:              Optional[ORBBacktestSignalDetail]
    short_signal:             Optional[ORBBacktestSignalDetail]

class ORBBacktestResponse(BaseModel):
    symbol:                  str
    from_date:               str
    to_date:                 str
    total_trading_days:      int
    days_with_long_signal:   int
    days_with_short_signal:  int
    days_with_strong_setup:  int
    results:                 list[ORBBacktestDayResult]
```

---

## Service (`backend/app/services/orb_backtest_service.py`)

```python
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.dhan_service import DhanService
from app.services.intraday_cache import IntradayCacheService
from app.schemas.orb import (
    ORBBacktestRequest, ORBBacktestResponse,
    ORBBacktestDayResult, ORBBacktestSignalDetail
)

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


class ORBBacktestService:

    def __init__(self, dhan: DhanService):
        self.dhan = dhan

    async def run_backtest(self, req: ORBBacktestRequest,
                           db) -> ORBBacktestResponse:
        from_date = date.fromisoformat(req.from_date)
        to_date   = date.fromisoformat(req.to_date)

        # Collect all weekdays in range
        trading_days = self._weekdays_in_range(from_date, to_date)

        # Pre-fetch all intraday data for range + one extra day before (for prev day volume)
        prefetch_from = self._prev_weekday(from_date)
        all_candles = await self.dhan.get_intraday_5min(
            req.security_id, req.exchange_segment, req.instrument_type,
            prefetch_from, to_date, db
        )

        # Group candles by date
        candles_by_date: dict[str, list] = {}
        for c in all_candles:
            candles_by_date.setdefault(c.trade_date, []).append(c)
        for d_str in candles_by_date:
            candles_by_date[d_str].sort(key=lambda c: c.candle_time)

        results = []
        for day in trading_days:
            day_str = str(day)
            candles = candles_by_date.get(day_str, [])

            # Filter to market hours
            candles = [c for c in candles if "09:15" <= c.candle_time <= "15:25"]

            if len(candles) < 4:
                # Not enough data (holiday or sparse data) — skip
                continue

            # Prev day volume
            prev_day_str = str(self._prev_weekday(day))
            prev_candles = candles_by_date.get(prev_day_str, [])
            second_half  = [c for c in prev_candles if c.candle_time >= "12:45"]
            prev_avg_vol = (sum(c.volume for c in second_half) / len(second_half)
                            if second_half else 0.0)

            # Criterion 1
            first = candles[0]
            wick_range = first.high - first.low
            body_pct   = abs(first.close - first.open) / wick_range if wick_range > 0 else 0.0
            direction  = "bullish" if first.close >= first.open else "bearish"
            vol_ratio  = first.volume / prev_avg_vol if prev_avg_vol > 0 else 0.0
            strong     = (body_pct >= req.body_pct_threshold and
                          vol_ratio >= req.volume_ratio_threshold)

            # Criterion 2
            orb_high = max(c.high for c in candles[:3])
            orb_low  = min(c.low  for c in candles[:3])

            # Criterion 3
            long_signal  = None
            short_signal = None

            for i in range(3, len(candles)):
                candle = candles[i]
                prev   = candles[i - 1]

                # LONG: candle CLOSE must be above orb_high (not just a wick)
                if long_signal is None and candle.close > orb_high and candle.volume > prev.volume:
                    long_signal = ORBBacktestSignalDetail(
                        breakout_time=candle.candle_time,
                        signal_price=candle.close,
                        breakout_candle_volume=candle.volume,
                        prev_candle_volume=prev.volume
                    )

                # SHORT: candle CLOSE must be below orb_low (not just a wick)
                if short_signal is None and candle.close < orb_low and candle.volume > prev.volume:
                    short_signal = ORBBacktestSignalDetail(
                        breakout_time=candle.candle_time,
                        signal_price=candle.close,
                        breakout_candle_volume=candle.volume,
                        prev_candle_volume=prev.volume
                    )

                if long_signal and short_signal:
                    break

            results.append(ORBBacktestDayResult(
                date=day_str,
                orb_high=round(orb_high, 2),
                orb_low=round(orb_low, 2),
                first_candle_direction=direction,
                first_candle_strong=strong,
                first_candle_body_pct=round(body_pct, 4),
                first_candle_volume_ratio=round(vol_ratio, 4),
                long_signal=long_signal,
                short_signal=short_signal,
            ))

        return ORBBacktestResponse(
            symbol=req.symbol,
            from_date=req.from_date,
            to_date=req.to_date,
            total_trading_days=len(results),
            days_with_long_signal=sum(1 for r in results if r.long_signal),
            days_with_short_signal=sum(1 for r in results if r.short_signal),
            days_with_strong_setup=sum(1 for r in results if r.first_candle_strong),
            results=results,
        )

    def _weekdays_in_range(self, from_date: date, to_date: date) -> list[date]:
        days = []
        d = from_date
        while d <= to_date:
            if d.weekday() < 5:
                days.append(d)
            d += timedelta(days=1)
        return days

    def _prev_weekday(self, d: date) -> date:
        d = d - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d
```

---

## Router endpoint (add to `routers/orb.py`)

```python
from app.services.orb_backtest_service import ORBBacktestService
from app.schemas.orb import ORBBacktestRequest, ORBBacktestResponse

@router.post("/backtest", response_model=ORBBacktestResponse)
async def run_orb_backtest(req: ORBBacktestRequest, db: Session = Depends(get_db)):
    from app.main import dhan_service
    svc = ORBBacktestService(dhan=dhan_service)
    return await svc.run_backtest(req, db)
```

---

## Performance Notes

- **Data volume:** 6 months × ~75 candles/day × 1 instrument ≈ 9,750 candles. All in-memory after first cache-fill.
- **Cache fill:** Dhan allows 90-day windows per request. A 6-month backtest needs 2 API calls. Subsequent backtests on the same symbol/range are fully cache-served.
- **Dhan API for indices:** Use `exchangeSegment="IDX_I"`, `instrument="INDEX"` for NIFTY/BANKNIFTY. Verify instrument_type string against Dhan annexure.

---

## Done When

- [ ] `POST /api/orb/backtest` returns results for a 1-month date range
- [ ] Long and short signal times are correctly identified
- [ ] Days with no data (holidays) are excluded from `total_trading_days`
- [ ] Repeated backtest calls on same date range are served from cache (no Dhan API calls)
- [ ] `days_with_long_signal`, `days_with_short_signal`, `days_with_strong_setup` counts match manual review of results
