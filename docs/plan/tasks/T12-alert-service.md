# T12 — AlertService + API

| Field | Value |
|-------|-------|
| Phase | 3 |
| Depends on | T08, T11 |
| Unlocks | T14, T19, T21 |
| Estimate | 1.5 days |
| Status | ⬜ Not Started |

## Goal
Implement full alert lifecycle management: CRUD operations, the periodic `check_alerts()` LTP-based trigger function, alert history tracking, and all REST API endpoints.

## Files to Create

- `backend/app/services/alert_service.py`
- `backend/app/routers/alerts.py`
- `backend/app/schemas/alert.py`

## Alert State Machine

```
created → active → triggered
               → expired (past expires_at)
               → deleted  (manual, soft-delete not needed — just DELETE row)
```

Trigger condition: `LTP <= alert_price`

## Steps

### 1. `backend/app/schemas/alert.py`

```python
from pydantic import BaseModel
from typing import Optional

class AlertCreate(BaseModel):
    symbol: str
    security_id: str
    signal_date: str
    alert_price: float
    valid_days: int = 30
    notes: Optional[str] = None

class AlertUpdate(BaseModel):
    alert_price: Optional[float] = None
    valid_days: Optional[int] = None
    notes: Optional[str] = None

class AlertRead(BaseModel):
    id: int
    symbol: str
    security_id: str
    signal_date: str
    alert_price: float
    valid_days: int
    expires_at: str
    status: str
    notes: Optional[str]
    created_at: str
    triggered_at: Optional[str]
    triggered_price: Optional[float]

    class Config:
        from_attributes = True

class AlertHistoryRead(BaseModel):
    id: int
    alert_id: int
    event_type: str
    price: Optional[float]
    note: Optional[str]
    timestamp: str

    class Config:
        from_attributes = True
```

### 2. `backend/app/services/alert_service.py`

```python
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.alert import Alert, AlertHistory
from app.services.dhan_service import get_dhan_service
from app.services.telegram_service import get_telegram_service

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_alert(db: Session, symbol: str, security_id: str, signal_date: str,
                 alert_price: float, valid_days: int, notes: str | None) -> Alert:
    now = datetime.now(IST)
    expires_at = (now + timedelta(days=valid_days)).isoformat()

    alert = Alert(
        symbol=symbol,
        security_id=security_id,
        signal_date=signal_date,
        alert_price=alert_price,
        valid_days=valid_days,
        expires_at=expires_at,
        status="active",
        notes=notes,
        created_at=now.isoformat(),
    )
    db.add(alert)
    db.flush()

    _log_event(db, alert.id, "created", price=alert_price, note="Alert created")
    db.commit()
    db.refresh(alert)
    return alert


def get_alerts(db: Session, status: str | None = None) -> list[Alert]:
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    return q.order_by(Alert.created_at.desc()).all()


def get_alert(db: Session, alert_id: int) -> Alert | None:
    return db.query(Alert).filter_by(id=alert_id).first()


def update_alert(db: Session, alert_id: int, alert_price: float | None,
                 valid_days: int | None, notes: str | None) -> Alert:
    alert = db.query(Alert).filter_by(id=alert_id).first()
    if not alert:
        raise ValueError(f"Alert {alert_id} not found")

    now = datetime.now(IST)
    changes = []

    if alert_price is not None and alert_price != alert.alert_price:
        alert.alert_price = alert_price
        changes.append(f"price → {alert_price}")

    if valid_days is not None and valid_days != alert.valid_days:
        alert.valid_days = valid_days
        # Recalculate expiry from created_at
        created = datetime.fromisoformat(alert.created_at)
        alert.expires_at = (created + timedelta(days=valid_days)).isoformat()
        changes.append(f"valid_days → {valid_days}")

    if notes is not None:
        alert.notes = notes
        changes.append("notes updated")

    if changes:
        _log_event(db, alert_id, "updated", note="; ".join(changes))

    db.commit()
    db.refresh(alert)
    return alert


def delete_alert(db: Session, alert_id: int):
    alert = db.query(Alert).filter_by(id=alert_id).first()
    if alert:
        _log_event(db, alert_id, "deleted")
        db.commit()
        db.delete(alert)
        db.commit()


def get_alert_history(db: Session, alert_id: int) -> list[AlertHistory]:
    return (db.query(AlertHistory)
            .filter_by(alert_id=alert_id)
            .order_by(AlertHistory.timestamp)
            .all())


def get_all_history(db: Session) -> list[AlertHistory]:
    return (db.query(AlertHistory)
            .order_by(AlertHistory.timestamp.desc())
            .limit(200)
            .all())


# ── Alert Monitor ─────────────────────────────────────────────────────────────

async def check_alerts(db: Session, bypass_window_guard: bool = False):
    """
    Main periodic function called by scheduler.
    1. Window guard (unless bypassed).
    2. Expire overdue alerts.
    3. Batch LTP fetch for all active alerts.
    4. Trigger any alerts where LTP <= alert_price.
    """
    now = datetime.now(IST)

    # Skip weekends
    if now.weekday() >= 5:
        return

    # Window guard
    if not bypass_window_guard:
        from app.services.config_service import get_config
        cfg = get_config(db)
        h_start, m_start = map(int, cfg.alert_check_start.split(":"))
        h_end,   m_end   = map(int, cfg.alert_check_end.split(":"))
        window_open  = now.replace(hour=h_start, minute=m_start, second=0, microsecond=0)
        window_close = now.replace(hour=h_end,   minute=m_end,   second=0, microsecond=0)
        # Truncate to minute so a cron at 15:30:00.003 still passes window_close of 15:30
        if not (window_open <= now.replace(second=0, microsecond=0) <= window_close):
            return

    # 1. Expire overdue alerts
    active_alerts = db.query(Alert).filter(Alert.status == "active").all()
    for alert in active_alerts:
        if datetime.fromisoformat(alert.expires_at) < now:
            alert.status = "expired"
            _log_event(db, alert.id, "expired")
    db.commit()

    # 2. Reload still-active alerts
    active_alerts = db.query(Alert).filter(Alert.status == "active").all()
    if not active_alerts:
        logger.debug("check_alerts: no active alerts.")
        return

    # 3. Batch LTP fetch
    by_segment: dict[str, list[str]] = {}
    for a in active_alerts:
        seg = "NSE_EQ"  # all alerts are NSE equities
        by_segment.setdefault(seg, []).append(a.security_id)

    dhan = get_dhan_service(db)
    try:
        ltp_data = dhan.get_ltp_batch(by_segment)
    except Exception as e:
        logger.error(f"LTP batch fetch failed in check_alerts: {e}")
        return

    # ltp_data: {"NSE_EQ": {"2885": 2441.50, ...}}
    ltp_flat: dict[str, float] = {}
    for seg, items in ltp_data.items():
        ltp_flat.update(items)

    # 4. Evaluate triggers
    telegram = get_telegram_service(db)
    for alert in active_alerts:
        ltp = ltp_flat.get(alert.security_id)
        if ltp is None:
            logger.warning(f"No LTP for {alert.symbol} ({alert.security_id})")
            continue

        if ltp <= alert.alert_price:
            alert.status = "triggered"
            alert.triggered_at = now.isoformat()
            alert.triggered_price = ltp
            _log_event(db, alert.id, "triggered", price=ltp,
                       note=f"LTP {ltp} <= alert {alert.alert_price}")
            db.commit()

            # Send Telegram notification (fire-and-forget; don't block)
            try:
                await telegram.send_alert_triggered(
                    symbol=alert.symbol,
                    signal_date=alert.signal_date,
                    alert_price=alert.alert_price,
                    triggered_price=ltp,
                )
            except Exception as e:
                logger.error(f"Telegram notification failed for alert {alert.id}: {e}")

    logger.info(f"check_alerts: evaluated {len(active_alerts)} alerts at {now.isoformat()}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log_event(db: Session, alert_id: int, event_type: str,
               price: float | None = None, note: str | None = None):
    db.add(AlertHistory(
        alert_id=alert_id,
        event_type=event_type,
        price=price,
        note=note,
        timestamp=datetime.now(IST).isoformat(),
    ))
```

### 3. `backend/app/routers/alerts.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import alert_service
from app.schemas.alert import AlertCreate, AlertUpdate, AlertRead, AlertHistoryRead

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_alerts(status: str | None = None, db: Session = Depends(get_db)):
    return alert_service.get_alerts(db, status=status)


@router.post("", response_model=AlertRead)
def create_alert(body: AlertCreate, db: Session = Depends(get_db)):
    return alert_service.create_alert(
        db, body.symbol, body.security_id, body.signal_date,
        body.alert_price, body.valid_days, body.notes
    )


@router.patch("/{alert_id}", response_model=AlertRead)
def update_alert(alert_id: int, body: AlertUpdate, db: Session = Depends(get_db)):
    try:
        return alert_service.update_alert(
            db, alert_id, body.alert_price, body.valid_days, body.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert_service.delete_alert(db, alert_id)
    return {"ok": True}


@router.get("/{alert_id}/history", response_model=list[AlertHistoryRead])
def get_alert_history(alert_id: int, db: Session = Depends(get_db)):
    return alert_service.get_alert_history(db, alert_id)


@router.get("/history/all", response_model=list[AlertHistoryRead])
def get_all_history(db: Session = Depends(get_db)):
    return alert_service.get_all_history(db)


@router.post("/check")
async def trigger_check(db: Session = Depends(get_db)):
    """Manual trigger for testing alert checking outside market hours."""
    await alert_service.check_alerts(db, bypass_window_guard=True)
    return {"ok": True}
```

### 4. Register router in `main.py`

```python
from app.routers import alerts
app.include_router(alerts.router)
```

## Done When
- `POST /api/alerts` creates an alert; status is `active`; `alert_history` has a `created` event
- `GET /api/alerts?status=active` returns only active alerts
- `PATCH /api/alerts/{id}` updates price/days; history event added
- `DELETE /api/alerts/{id}` removes alert; history event added before delete
- `GET /api/alerts/{id}/history` returns event log in chronological order
- `POST /api/alerts/check` triggers evaluation and returns immediately
- Alert with LTP <= alert_price gets status `triggered` + Telegram message sent
- Alert past its `expires_at` gets status `expired` on next check
