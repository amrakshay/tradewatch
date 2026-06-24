from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import scanner_service

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
