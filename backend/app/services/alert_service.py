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
