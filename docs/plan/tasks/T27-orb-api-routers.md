# T27 — ORB API Routers

**Phase:** ORB Phase 1
**Depends on:** T25 (ORBScannerService), T23 (schema)
**Blocks:** T30 (frontend)

---

## Goal

Implement FastAPI routers for ORB universe management, signal retrieval, and manual scan trigger.

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `backend/app/routers/orb.py` |
| Modify | `backend/app/main.py` (register router) |
| Create | `backend/app/schemas/orb.py` (Pydantic schemas) |

---

## Pydantic Schemas (`backend/app/schemas/orb.py`)

```python
from pydantic import BaseModel
from typing import Optional

class ORBUniverseCreate(BaseModel):
    symbol:           str
    security_id:      str
    exchange_segment: str = "IDX_I"
    instrument_type:  str = "INDEX"

class ORBUniverseResponse(BaseModel):
    id:               int
    symbol:           str
    security_id:      str
    exchange_segment: str
    instrument_type:  str
    is_active:        bool
    added_at:         str

class ORBSignalResponse(BaseModel):
    id:                        int
    signal_date:               str
    symbol:                    str
    security_id:               str
    # First candle
    first_candle_open:         float
    first_candle_high:         float
    first_candle_low:          float
    first_candle_close:        float
    first_candle_volume:       int
    first_candle_direction:    str
    first_candle_body_pct:     float
    first_candle_volume_ratio: float
    first_candle_strong:       bool
    prev_day_avg_volume:       float
    # Range
    orb_high:                  float
    orb_low:                   float
    # Breakout
    signal_direction:          str
    breakout_time:             str
    breakout_candle_open:      float
    breakout_candle_high:      float
    breakout_candle_low:       float
    breakout_candle_close:     float
    breakout_candle_volume:    int
    prev_candle_volume:        int
    signal_price:              float
    created_at:                str
```

---

## Router (`backend/app/routers/orb.py`)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database import get_db
from app.models.orb import ORBUniverse, ORBSignal
from app.schemas.orb import ORBUniverseCreate, ORBUniverseResponse, ORBSignalResponse
from app.services.orb_scanner_service import ORBScannerService
# Import service singleton from main (or use dependency injection)

IST = ZoneInfo("Asia/Kolkata")
router = APIRouter(prefix="/api/orb", tags=["orb"])

# --- Universe ---

@router.get("/universe", response_model=list[ORBUniverseResponse])
def list_orb_universe(db: Session = Depends(get_db)):
    return db.query(ORBUniverse).order_by(ORBUniverse.symbol).all()

@router.post("/universe", response_model=ORBUniverseResponse, status_code=201)
def add_orb_instrument(body: ORBUniverseCreate, db: Session = Depends(get_db)):
    existing = db.query(ORBUniverse).filter_by(security_id=body.security_id).first()
    if existing:
        raise HTTPException(400, "Instrument with this security_id already exists")
    inst = ORBUniverse(
        **body.dict(),
        is_active=1,
        added_at=datetime.now(IST).isoformat()
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst

@router.patch("/universe/{id}")
def toggle_orb_instrument(id: int, is_active: bool, db: Session = Depends(get_db)):
    inst = db.query(ORBUniverse).get(id)
    if not inst:
        raise HTTPException(404, "Instrument not found")
    inst.is_active = 1 if is_active else 0
    db.commit()
    return {"ok": True}

@router.delete("/universe/{id}")
def delete_orb_instrument(id: int, db: Session = Depends(get_db)):
    inst = db.query(ORBUniverse).get(id)
    if not inst:
        raise HTTPException(404, "Instrument not found")
    db.delete(inst)
    db.commit()
    return {"ok": True}

# --- Signals ---

@router.get("/signals/dates")
def get_orb_signal_dates(db: Session = Depends(get_db)):
    rows = (db.query(ORBSignal.signal_date)
            .distinct()
            .order_by(ORBSignal.signal_date.desc())
            .all())
    return {"dates": [r.signal_date for r in rows]}

@router.get("/signals/latest")
def get_latest_orb_signals(db: Session = Depends(get_db)):
    latest_date = (db.query(ORBSignal.signal_date)
                   .order_by(ORBSignal.signal_date.desc())
                   .first())
    if not latest_date:
        return {"date": None, "count": 0, "signals": []}
    return _signals_for_date(latest_date.signal_date, db)

@router.get("/signals")
def get_orb_signals(date: str, db: Session = Depends(get_db)):
    return _signals_for_date(date, db)

def _signals_for_date(date_str: str, db: Session):
    signals = (db.query(ORBSignal)
               .filter_by(signal_date=date_str)
               .order_by(ORBSignal.created_at)
               .all())
    return {
        "date": date_str,
        "count": len(signals),
        "signals": signals
    }

# --- Manual trigger ---

@router.post("/scanner/run")
async def run_orb_scan_now(db: Session = Depends(get_db)):
    """Manually trigger the ORB check right now."""
    from app.main import orb_scanner_service   # or via DI
    new_signals = await orb_scanner_service.run_orb_check()
    return {
        "triggered_at": datetime.now(IST).isoformat(),
        "new_signals_count": len(new_signals)
    }
```

### Register in `main.py`

```python
from app.routers import orb as orb_router
app.include_router(orb_router.router)
```

---

## Done When

- [ ] `GET /api/orb/universe` returns list of instruments
- [ ] `POST /api/orb/universe` adds new instrument; rejects duplicate security_id
- [ ] `PATCH /api/orb/universe/{id}` toggles is_active
- [ ] `DELETE /api/orb/universe/{id}` removes instrument
- [ ] `GET /api/orb/signals?date=YYYY-MM-DD` returns signals for that date
- [ ] `GET /api/orb/signals/dates` returns all dates with signals, newest first
- [ ] `GET /api/orb/signals/latest` returns most recent date's signals
- [ ] `POST /api/orb/scanner/run` triggers scan and returns count of new signals
- [ ] All endpoints documented in Swagger at `localhost:8000/docs`
