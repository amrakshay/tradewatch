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


@router.get("/history/all", response_model=list[AlertHistoryRead])
def get_all_history(db: Session = Depends(get_db)):
    return alert_service.get_all_history(db)


@router.post("/check")
async def trigger_check(db: Session = Depends(get_db)):
    """Manual trigger for testing alert checking outside market hours."""
    await alert_service.check_alerts(db, bypass_window_guard=True)
    return {"ok": True}


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
