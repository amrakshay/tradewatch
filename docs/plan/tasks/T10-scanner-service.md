# T10 — ScannerService + API

| Field | Value |
|-------|-------|
| Phase | 2 |
| Depends on | T08, T09 |
| Unlocks | T14, T18, T21 |
| Estimate | 1.5 days |
| Status | ⬜ Not Started |

## Goal
Implement the core daily scan logic: fetch OHLC for all active stocks, compute N-day returns, persist qualifying signals, and expose the signals API endpoints.

## Files to Create

- `backend/app/services/scanner_service.py`
- `backend/app/routers/signals.py`
- `backend/app/schemas/signal.py`

## Scan Logic

```
return_pct = (close[today] - close[N trading days ago]) / close[N trading days ago] * 100
qualifies  = return_pct >= threshold
```

`close[N trading days ago]` is `candles[-N-1].close` when the list is sorted ascending and today is the last entry. Since Dhan daily data only contains trading days, index `-N-1` automatically points to the Nth prior trading day.

## Steps

### 1. `backend/app/services/scanner_service.py`

```python
import asyncio
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.models.signal import ScanSignal
from app.models.stock import Stock
from app.services.dhan_service import get_dhan_service
from app.services.config_service import get_decrypted_config

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


async def run_scan(db: Session, scan_date: date | None = None) -> dict:
    """
    Scan all active stocks for the given date (defaults to today IST).
    Returns summary: {scan_date, total_scanned, qualified, skipped, signals: [...]}
    """
    cfg = get_decrypted_config(db)
    scan_date = scan_date or datetime.now(IST).date()
    scan_date_str = scan_date.strftime("%Y-%m-%d")
    threshold = cfg["scan_percentage"]
    num_days = cfg["scan_days"]

    # Lookback: fetch 14 calendar days before scan_date for buffer
    from_date = (scan_date - timedelta(days=14)).strftime("%Y-%m-%d")
    to_date = scan_date_str

    stocks = db.query(Stock).filter(Stock.is_active == 1).all()
    dhan = get_dhan_service(db)

    qualified = []
    skipped = 0

    async def process_stock(stock: Stock):
        nonlocal skipped
        try:
            candles = await dhan.get_daily_ohlc(
                security_id=stock.security_id,
                from_date=from_date,
                to_date=to_date,
                db=db,
                exchange_segment=stock.exchange_segment,
            )

            # Filter to only include candles up to and including scan_date
            candles = [c for c in candles if c["date"] <= scan_date_str]

            # Need at least num_days + 1 candles
            if len(candles) < num_days + 1:
                logger.debug(f"{stock.symbol}: insufficient candles ({len(candles)}), skipping.")
                skipped += 1
                return

            today_close = candles[-1]["close"]
            start_close = candles[-(num_days + 1)]["close"]

            if start_close == 0:
                skipped += 1
                return

            ret_pct = (today_close - start_close) / start_close * 100

            if ret_pct >= threshold:
                qualified.append({
                    "symbol": stock.symbol,
                    "security_id": stock.security_id,
                    "close_price": today_close,
                    "start_price": start_close,
                    "return_pct": round(ret_pct, 2),
                })
        except Exception as e:
            logger.error(f"Error scanning {stock.symbol}: {e}")
            skipped += 1

    # Process all stocks (semaphore in DhanService limits Dhan API concurrency)
    await asyncio.gather(*[process_stock(s) for s in stocks])

    # Persist signals
    _persist_signals(db, scan_date_str, qualified, num_days, threshold)

    return {
        "scan_date": scan_date_str,
        "total_scanned": len(stocks),
        "qualified": len(qualified),
        "skipped": skipped,
        "signals": qualified,
    }


def _persist_signals(db: Session, scan_date: str, signals: list[dict],
                     scan_days: int, scan_threshold: float):
    """Upsert scan signals. Skips if no signals (market holiday detection)."""
    if not signals:
        logger.info(f"No signals for {scan_date} — possible market holiday or no qualifying stocks.")
        return

    for s in signals:
        existing = (db.query(ScanSignal)
                    .filter_by(scan_date=scan_date, security_id=s["security_id"])
                    .first())
        if existing:
            continue
        db.add(ScanSignal(
            scan_date=scan_date,
            symbol=s["symbol"],
            security_id=s["security_id"],
            close_price=s["close_price"],
            start_price=s["start_price"],
            return_pct=s["return_pct"],
            scan_days=scan_days,
            scan_threshold=scan_threshold,
            created_at=datetime.now(IST).isoformat(),
        ))
    db.commit()
    logger.info(f"Scan {scan_date}: {len(signals)} signals persisted.")


def get_signals_for_date(db: Session, scan_date: str, alert_security_ids: set = None) -> list:
    rows = (db.query(ScanSignal)
            .filter(ScanSignal.scan_date == scan_date)
            .order_by(ScanSignal.return_pct.desc())
            .all())
    # Optionally annotate with has_alert
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "symbol": r.symbol,
            "security_id": r.security_id,
            "close_price": r.close_price,
            "start_price": r.start_price,
            "return_pct": r.return_pct,
            "scan_days": r.scan_days,
            "scan_threshold": r.scan_threshold,
            "has_alert": r.security_id in (alert_security_ids or set()),
        })
    return result


def get_signal_dates(db: Session) -> list[str]:
    from sqlalchemy import distinct
    rows = db.query(distinct(ScanSignal.scan_date)).order_by(ScanSignal.scan_date.desc()).all()
    return [r[0] for r in rows]
```

### 2. `backend/app/schemas/signal.py`

```python
from pydantic import BaseModel

class SignalRead(BaseModel):
    id: int
    symbol: str
    security_id: str
    close_price: float
    start_price: float
    return_pct: float
    scan_days: int
    scan_threshold: float
    has_alert: bool = False
```

### 3. `backend/app/routers/signals.py`

```python
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo
from app.database import get_db
from app.services import scanner_service

IST = ZoneInfo("Asia/Kolkata")
router = APIRouter(prefix="/api", tags=["signals"])

@router.get("/signals")
def get_signals(date: str, db: Session = Depends(get_db)):
    from app.models.alert import Alert
    active_alerts = db.query(Alert.security_id).filter(Alert.status == "active").all()
    active_sids = {r.security_id for r in active_alerts}
    signals = scanner_service.get_signals_for_date(db, date, active_sids)
    return {"date": date, "count": len(signals), "signals": signals}

@router.get("/signals/dates")
def get_signal_dates(db: Session = Depends(get_db)):
    return scanner_service.get_signal_dates(db)

@router.get("/signals/latest")
def get_latest_signals(db: Session = Depends(get_db)):
    dates = scanner_service.get_signal_dates(db)
    if not dates:
        return {"date": None, "signals": []}
    latest = dates[0]
    signals = scanner_service.get_signals_for_date(db, latest)
    return {"date": latest, "count": len(signals), "signals": signals}

@router.post("/scanner/run")
async def run_scanner(db: Session = Depends(get_db)):
    result = await scanner_service.run_scan(db)
    return result
```

### 4. Register router in `main.py`

```python
from app.routers import signals
app.include_router(signals.router)
```

## Done When
- `POST /api/scanner/run` returns `{scan_date, total_scanned, qualified, signals: [...]}`
- Signals are persisted to DB; re-running same day does not duplicate
- `GET /api/signals?date=YYYY-MM-DD` returns signals for that date sorted by `return_pct` desc
- `GET /api/signals/dates` returns list of dates with scans, most recent first
- When Dhan returns no data (holiday), scan logs and skips gracefully with no error
