# T05 — TokenService

| Field | Value |
|-------|-------|
| Phase | 1 |
| Depends on | T04 |
| Unlocks | T14, T15 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the service that manages the Dhan access token lifecycle: checks validity on startup, renews it daily at 09:00 IST, updates `token_status` and `token_expires_at` in the DB, and fires a Telegram alert if renewal fails.

## Files to Create

- `backend/app/services/token_service.py`

## Key Dhan API Calls

| Call | Endpoint | When used |
|------|----------|-----------|
| Check validity | `GET https://api.dhan.co/v2/profile` | On startup, after every renew |
| Renew token | `POST https://api.dhan.co/v2/RenewToken` | Daily 09:00 job + proactive on startup |

Headers for both: `access-token: <current_token>`, `dhanClientId: <client_id>`

Profile response field: `tokenValidity` — format `"DD/MM/YYYY HH:MM"` IST.

## Steps

### `backend/app/services/token_service.py`

```python
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


async def check_token_validity(db: Session) -> str:
    """
    Call GET /v2/profile with current token.
    Returns: 'active' | 'expiring_soon' | 'expired' | 'error'
    Also updates token_status + token_expires_at in DB.
    """
    cfg = get_decrypted_config(db)
    if not cfg["dhan_access_token"] or not cfg["dhan_client_id"]:
        return _set_status(db, "unknown")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{DHAN_BASE}/profile",
                headers=_auth_headers(cfg["dhan_client_id"], cfg["dhan_access_token"])
            )
        if resp.status_code == 401:
            return _set_status(db, "expired")

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
                headers=_auth_headers(cfg["dhan_client_id"], cfg["dhan_access_token"])
            )

        if resp.status_code != 200:
            logger.error(f"Token renewal failed: {resp.status_code} {resp.text}")
            return False

        data = resp.json()
        new_token = data.get("accessToken", "")
        expiry_str = data.get("expiryTime", "")    # ISO format from Dhan

        if not new_token:
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


def _set_status(db: Session, status: str, row=None, commit: bool = False) -> str:
    if row is None:
        row = db.query(AppConfig).filter(AppConfig.id == 1).first()
    row.token_status = status
    if commit:
        db.commit()
    return status
```

### Startup token check (called from `main.py`)

```python
async def startup_token_check(db: Session):
    status = await check_token_validity(db)
    logger.info(f"Token status on startup: {status}")

    if status == "expiring_soon":
        logger.info("Token expiring soon — renewing proactively.")
        await renew_token(db)

    elif status == "expired":
        logger.warning("Dhan token expired. Scanner/alerts paused.")
        # TelegramService will be wired in T14 startup sequence
        # For now, just log — Telegram send is added after T11 is done
```

### Scheduled job (registered in T14)

```python
async def token_renew_job(db_factory):
    """Run at 09:00 IST daily."""
    db = db_factory()
    try:
        success = await renew_token(db)
        if not success:
            # Fire Telegram alert — wired after T11
            logger.error("Daily token renewal failed. Manual intervention needed.")
    finally:
        db.close()
```

## Done When
- `check_token_validity(db)` returns correct status given a valid / expired token
- `renew_token(db)` updates `dhan_access_token` in DB with newly encrypted token
- `token_expires_at` and `token_status` are correctly updated in both calls
- Calling renew with an expired token gracefully returns `False` (no crash)
