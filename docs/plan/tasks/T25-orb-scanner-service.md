# T25 — ORBScannerService

**Phase:** ORB Phase 1
**Depends on:** T23, T24, T29 (TelegramService ORB notification)
**Blocks:** T26, T27

---

## Goal

Implement the core ORB signal detection logic: evaluate the first 5-min candle, establish the opening range, detect breakouts, persist signals, and fire Telegram notifications.

---

## Files to Create

| Action | File |
|--------|------|
| Create | `backend/app/services/orb_scanner_service.py` |

---

## Implementation

```python
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.orb import ORBUniverse, ORBSignal
from app.schemas.orb import IntradayCandle
from app.services.dhan_service import DhanService
from app.services.telegram_service import TelegramService
from app.services.config_service import ConfigService

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


class ORBScannerService:

    def __init__(self, dhan: DhanService, telegram: TelegramService,
                 config: ConfigService, db: Session):
        self.dhan     = dhan
        self.telegram = telegram
        self.config   = config
        self.db       = db

    # -------------------------------------------------------------------------
    # Entry point called by scheduler every 5 mins
    # -------------------------------------------------------------------------

    async def run_orb_check(self) -> list[ORBSignal]:
        now = datetime.now(IST)
        today = now.date()

        if now.weekday() >= 5:
            return []

        open_time  = now.replace(hour=9,  minute=25, second=0, microsecond=0)
        close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if not (open_time <= now <= close_time):
            return []

        instruments = (self.db.query(ORBUniverse)
                       .filter_by(is_active=1).all())
        new_signals = []
        for inst in instruments:
            try:
                sigs = await self._process_instrument(inst, today)
                new_signals.extend(sigs)
            except Exception as e:
                logger.error(f"ORB check failed for {inst.symbol}: {e}")

        return new_signals

    # -------------------------------------------------------------------------
    # Per-instrument logic
    # -------------------------------------------------------------------------

    async def _process_instrument(self, instrument: ORBUniverse,
                                   today: date) -> list[ORBSignal]:
        candles = await self.dhan.get_intraday_5min(
            instrument.security_id,
            instrument.exchange_segment,
            instrument.instrument_type,
            today, today,
            self.db
        )

        # Filter to today's market candles only (9:15 onwards)
        candles = [c for c in candles if c.candle_time >= "09:15"]

        if len(candles) < 1:
            return []

        # --- Criterion 1: First candle ---
        first = candles[0]  # 9:15 candle
        first_data = self._evaluate_first_candle(first, instrument, today)

        # --- Criterion 2: Range needs 3 candles (9:15, 9:20, 9:25) ---
        if len(candles) < 3:
            return []

        orb_high = max(c.high for c in candles[:3])
        orb_low  = min(c.low  for c in candles[:3])

        # --- Criterion 3: Breakout from candle index 3 onwards (9:35+) ---
        if len(candles) < 4:
            return []

        existing_long  = self._get_existing_signal(today, instrument.security_id, "LONG")
        existing_short = self._get_existing_signal(today, instrument.security_id, "SHORT")

        new_signals = []
        for i in range(3, len(candles)):
            candle = candles[i]
            prev   = candles[i - 1]

            # Long: candle must CLOSE above orb_high (not just wick through it)
            # + breakout candle volume must exceed the previous candle's volume
            if not existing_long and candle.close > orb_high and candle.volume > prev.volume:
                sig = self._save_signal(
                    direction="LONG", today=today, instrument=instrument,
                    first_data=first_data, orb_high=orb_high, orb_low=orb_low,
                    candle=candle, prev=prev
                )
                await self.telegram.send_orb_signal(sig)
                existing_long = sig
                new_signals.append(sig)

            # Short: candle must CLOSE below orb_low (not just wick through it)
            if not existing_short and candle.close < orb_low and candle.volume > prev.volume:
                sig = self._save_signal(
                    direction="SHORT", today=today, instrument=instrument,
                    first_data=first_data, orb_high=orb_high, orb_low=orb_low,
                    candle=candle, prev=prev
                )
                await self.telegram.send_orb_signal(sig)
                existing_short = sig
                new_signals.append(sig)

        return new_signals

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _evaluate_first_candle(self, candle: IntradayCandle,
                                instrument: ORBUniverse, today: date) -> dict:
        wick_range = candle.high - candle.low
        body_pct = abs(candle.close - candle.open) / wick_range if wick_range > 0 else 0.0
        direction = "bullish" if candle.close >= candle.open else "bearish"

        prev_day_avg_vol = self._get_prev_day_2nd_half_avg_volume(instrument, today)
        volume_ratio = candle.volume / prev_day_avg_vol if prev_day_avg_vol > 0 else 0.0

        cfg = self.config.get()
        strong = (body_pct >= cfg.orb_body_pct_threshold and
                  volume_ratio >= cfg.orb_volume_ratio_threshold)

        return dict(
            first_candle_open=candle.open, first_candle_high=candle.high,
            first_candle_low=candle.low,  first_candle_close=candle.close,
            first_candle_volume=candle.volume,
            first_candle_direction=direction,
            first_candle_body_pct=round(body_pct, 4),
            first_candle_volume_ratio=round(volume_ratio, 4),
            first_candle_strong=1 if strong else 0,
            prev_day_avg_volume=round(prev_day_avg_vol, 2),
        )

    def _get_prev_day_2nd_half_avg_volume(self, instrument: ORBUniverse,
                                           today: date) -> float:
        prev_day = self._prev_trading_day(today)
        # get_intraday_5min is async; call synchronously via cached data
        # (prev day is always a past date → served from cache after first fetch)
        candles = self.db.query(__import__('app.models.orb', fromlist=['IntradayCandleCache']).IntradayCandleCache).filter(
            __import__('app.models.orb', fromlist=['IntradayCandleCache']).IntradayCandleCache.security_id == instrument.security_id,
            __import__('app.models.orb', fromlist=['IntradayCandleCache']).IntradayCandleCache.trade_date == str(prev_day),
            __import__('app.models.orb', fromlist=['IntradayCandleCache']).IntradayCandleCache.interval_mins == 5,
            __import__('app.models.orb', fromlist=['IntradayCandleCache']).IntradayCandleCache.candle_time >= "12:45",
        ).all()

        if not candles:
            return 0.0
        return sum(c.volume for c in candles) / len(candles)

    def _prev_trading_day(self, today: date) -> date:
        d = today - timedelta(days=1)
        while d.weekday() >= 5:   # skip weekends (holidays: Dhan returns empty, handled gracefully)
            d -= timedelta(days=1)
        return d

    def _get_existing_signal(self, today: date, security_id: str,
                              direction: str):
        return (self.db.query(ORBSignal)
                .filter_by(signal_date=str(today),
                           security_id=security_id,
                           signal_direction=direction)
                .first())

    def _save_signal(self, direction: str, today: date,
                     instrument: ORBUniverse, first_data: dict,
                     orb_high: float, orb_low: float,
                     candle: IntradayCandle,
                     prev: IntradayCandle) -> ORBSignal:
        from datetime import datetime
        sig = ORBSignal(
            signal_date=str(today),
            symbol=instrument.symbol,
            security_id=instrument.security_id,
            **first_data,
            orb_high=orb_high,
            orb_low=orb_low,
            signal_direction=direction,
            breakout_time=candle.candle_time,
            breakout_candle_open=candle.open,
            breakout_candle_high=candle.high,
            breakout_candle_low=candle.low,
            breakout_candle_close=candle.close,
            breakout_candle_volume=candle.volume,
            prev_candle_volume=prev.volume,
            signal_price=candle.close,
            telegram_sent=0,
            created_at=datetime.now(IST).isoformat(),
        )
        self.db.add(sig)
        self.db.commit()
        self.db.refresh(sig)
        logger.info(f"ORB {direction} signal: {instrument.symbol} @ {candle.candle_time} "
                    f"price={candle.close}")
        return sig
```

### Note on async / prev-day volume

The `_get_prev_day_2nd_half_avg_volume` method queries the cache synchronously via SQLAlchemy. This works because:
- Previous trading day is always a past date → fetched from Dhan and stored in `intraday_candle_cache` during backtest warmup or the first time the ORB scanner processes that instrument
- If the cache is empty for the previous day (first ever run), return 0.0 → `volume_ratio` will be 0 → `first_candle_strong = False`. This is acceptable — the signal still fires if breakout criteria are met.

To pre-warm the cache, the ORB scanner on its first run should proactively fetch the previous day's data via `get_intraday_5min()` (async) before the synchronous volume lookup.

---

## Done When

- [ ] `run_orb_check()` returns empty list before 9:25 AM IST and after 15:30 IST
- [ ] `run_orb_check()` returns empty list on weekends
- [ ] First candle body_pct and volume_ratio computed correctly
- [ ] `orb_high` and `orb_low` correctly span all 3 opening range candles
- [ ] Long signal fires when close > orb_high AND volume > prev volume (only once per day)
- [ ] Short signal fires when close < orb_low AND volume > prev volume (only once per day)
- [ ] Both signals can coexist on same day
- [ ] Signal row persisted to `orb_signals` with all fields populated
- [ ] `telegram_sent` set to 1 after successful Telegram notification
