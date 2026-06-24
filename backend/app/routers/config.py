from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.config_service import get_config_for_api, update_config
from app.services.token_service import check_token_validity, renew_token
from app.services.telegram_service import get_telegram_service
from app.schemas.config import ConfigRead, ConfigUpdate

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigRead)
def get_config_endpoint(db: Session = Depends(get_db)):
    return get_config_for_api(db)


@router.put("", response_model=ConfigRead)
def update_config_endpoint(body: ConfigUpdate, db: Session = Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    return update_config(db, body)


@router.post("/test-dhan")
async def test_dhan_connection(db: Session = Depends(get_db)):
    """
    Check token validity via GET /v2/profile.
    Returns {valid: bool, message: str, expires_at: str|None}.
    """
    from app.models.config import AppConfig
    status = await check_token_validity(db)
    row = db.query(AppConfig).filter(AppConfig.id == 1).first()
    valid = status in ("active", "expiring_soon")
    messages = {
        "active": "Token is valid.",
        "expiring_soon": "Token is valid but expiring soon.",
        "expired": "Token has expired. Please renew or re-enter a new token.",
        "error": "Failed to reach Dhan API. Check credentials and connectivity.",
        "unknown": "No credentials configured.",
    }
    return {
        "valid": valid,
        "message": messages.get(status, status),
        "expires_at": row.token_expires_at if row else None,
    }


@router.post("/renew-token")
async def renew_dhan_token(db: Session = Depends(get_db)):
    """
    Manually trigger POST /v2/RenewToken.
    Returns {success: bool, message: str, new_expires_at: str|None}.
    """
    from app.models.config import AppConfig
    success = await renew_token(db)
    row = db.query(AppConfig).filter(AppConfig.id == 1).first()
    return {
        "success": success,
        "message": "Token renewed successfully." if success else "Token renewal failed. The current token may already be expired.",
        "new_expires_at": row.token_expires_at if (success and row) else None,
    }


@router.post("/test-telegram")
async def test_telegram(db: Session = Depends(get_db)):
    """
    Send a test message via the configured Telegram bot.
    Returns {sent: bool}.
    """
    svc = get_telegram_service(db)
    sent = await svc.send_test_message()
    return {"sent": sent}
