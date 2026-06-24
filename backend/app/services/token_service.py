import httpx
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.services.config_service import get_decrypted_config
from app.models.config import AppConfig

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

DHAN_BASE = "https://api.dhan.co/v2"


def _auth_headers(client_id: str, access_token: str) -> dict:
    return {
        "access-token": access_token,
        "dhanClientId": client_id,
        "Content-Type": "application/json",
    }


def _parse_dhan_expiry(validity_str: str) -> datetime:
    """Parse Dhan's tokenValidity string 'DD/MM/YYYY HH:MM' to IST datetime."""
    return datetime.strptime(validity_str, "%d/%m/%Y %H:%M").replace(tzinfo=IST)


def _set_status(db: Session, status: str, row=None, commit: bool = False) -> str:
    if row is None:
        row = db.query(AppConfig).filter(AppConfig.id == 1).first()
    row.token_status = status
    if commit:
        db.commit()
    return status


async def check_token_validity(db: Session) -> str:
    """
    Call GET /v2/profile with current token.
    Returns: 'active' | 'expiring_soon' | 'expired' | 'error' | 'unknown'
    Also updates token_status + token_expires_at in DB.
    """
    cfg = get_decrypted_config(db)
    if not cfg["dhan_access_token"] or not cfg["dhan_client_id"]:
        return _set_status(db, "unknown")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{DHAN_BASE}/profile",
                headers=_auth_headers(cfg["dhan_client_id"], cfg["dhan_access_token"]),
            )
        if resp.status_code == 401:
            return _set_status(db, "expired", commit=True)

        data = resp.json()
        validity_str = data.get("tokenValidity", "")
        if not validity_str:
            return _set_status(db, "error")

        expiry = _parse_dhan_expiry(validity_str)
        now = datetime.now(IST)
        row = db.query(AppConfig).filter(AppConfig.id == 1).first()
        row.token_expires_at = expiry.isoformat()

        if expiry <= now:
            return _set_status(db, "expired", row=row, commit=True)
        elif expiry - now <= timedelta(hours=2):
            return _set_status(db, "expiring_soon", row=row, commit=True)
        else:
            return _set_status(db, "active", row=row, commit=True)

    except Exception as e:
        logger.error(f"Token validity check failed: {e}")
        return _set_status(db, "error")


async def renew_token(db: Session) -> bool:
    """
    Call POST /v2/RenewToken. On success, encrypt + save new token.
    Returns True on success, False on failure.
    Only works if current token is still active.
    """
    cfg = get_decrypted_config(db)
    if not cfg["dhan_access_token"] or not cfg["dhan_client_id"]:
        logger.warning("Cannot renew: no token/client_id configured.")
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{DHAN_BASE}/RenewToken",
                headers=_auth_headers(cfg["dhan_client_id"], cfg["dhan_access_token"]),
            )

        if resp.status_code != 200:
            logger.error(f"Token renewal failed: {resp.status_code} {resp.text}")
            return False

        data = resp.json()
        new_token = data.get("accessToken", "")
        expiry_str = data.get("expiryTime", "")

        if not new_token:
            logger.error("Token renewal response missing accessToken.")
            return False

        from app.services.encryption import encryption_service

        row = db.query(AppConfig).filter(AppConfig.id == 1).first()
        row.dhan_access_token = encryption_service.encrypt(new_token)
        row.token_expires_at = expiry_str
        row.token_status = "active"
        row.updated_at = datetime.now(IST).isoformat()
        db.commit()

        logger.info(f"Token renewed successfully. Expires: {expiry_str}")
        return True

    except Exception as e:
        logger.error(f"Token renewal exception: {e}")
        return False


async def startup_token_check(db: Session):
    """Run on FastAPI startup: validate token and renew proactively if expiring soon."""
    status = await check_token_validity(db)
    logger.info(f"Token status on startup: {status}")

    if status == "expiring_soon":
        logger.info("Token expiring soon — renewing proactively.")
        await renew_token(db)
    elif status == "expired":
        logger.warning("Dhan token expired. Scanner/alerts paused.")
        # Telegram alert wired in T14 once TelegramService is available


async def token_renew_job(db_factory):
    """Scheduled job — run at 09:00 IST daily."""
    db = db_factory()
    try:
        success = await renew_token(db)
        if not success:
            logger.error("Daily token renewal failed. Manual intervention needed.")
            # Telegram alert wired in T14 once TelegramService is available
    finally:
        db.close()
