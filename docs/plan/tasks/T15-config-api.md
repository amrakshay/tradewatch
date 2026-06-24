# T15 — Config API

| Field | Value |
|-------|-------|
| Phase | 2 |
| Depends on | T04, T05 |
| Unlocks | T17 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Expose REST endpoints for reading and updating app configuration. Sensitive fields (tokens) are masked in GET responses. On save, the ConfigService dispatches side effects (scheduler reschedule, service re-init).

## Files to Create

- `backend/app/routers/config.py`
- `backend/app/schemas/config.py`

## Steps

### 1. `backend/app/schemas/config.py`

```python
from pydantic import BaseModel
from typing import Optional

class ConfigRead(BaseModel):
    scan_time: str
    scan_percentage: float
    scan_days: int
    alert_check_interval_mins: int
    alert_check_start: str
    alert_check_end: str
    dhan_client_id: str
    dhan_access_token: str       # masked: "tw-xxxx" or empty
    token_expires_at: Optional[str]
    token_status: str
    telegram_bot_token: str      # masked
    telegram_chat_id: str

class ConfigUpdate(BaseModel):
    scan_time: Optional[str] = None
    scan_percentage: Optional[float] = None
    scan_days: Optional[int] = None
    alert_check_interval_mins: Optional[int] = None
    alert_check_start: Optional[str] = None
    alert_check_end: Optional[str] = None
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
```

### 2. `backend/app/routers/config.py`

```python
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


@router.put("")
def update_config_endpoint(body: ConfigUpdate, db: Session = Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    update_config(db, updates)
    return get_config_for_api(db)


@router.post("/test-dhan")
async def test_dhan_connection(db: Session = Depends(get_db)):
    """
    Check token validity via GET /v2/profile.
    Returns {valid: bool, message: str, expires_at: str|None}.
    """
    result = await check_token_validity(db)
    return result


@router.post("/renew-token")
async def renew_dhan_token(db: Session = Depends(get_db)):
    """
    Manually trigger POST /v2/RenewToken.
    Returns {success: bool, message: str, new_expires_at: str|None}.
    """
    result = await renew_token(db)
    return result


@router.post("/test-telegram")
async def test_telegram(db: Session = Depends(get_db)):
    """
    Send a test message via the configured Telegram bot.
    Returns {sent: bool}.
    """
    svc = get_telegram_service(db)
    sent = await svc.send_test_message()
    return {"sent": sent}
```

### 3. Register router in `main.py`

```python
from app.routers import config
app.include_router(config.router)
```

## Masking Behavior

`get_config_for_api()` (implemented in T04 ConfigService) returns masked token display values: the first 4 chars + "…" for non-empty values, empty string if unset.

The `update_config()` function in ConfigService checks `_is_masked(value)` before writing — if the frontend sends back a masked display value unchanged, it is silently ignored (no overwrite).

## Done When
- `GET /api/config` returns config with `dhan_access_token` masked (never plaintext)
- `PUT /api/config` with `{"scan_time": "16:00"}` updates scan_time and reschedules the job
- `PUT /api/config` with a masked token value does NOT overwrite the actual stored token
- `POST /api/config/test-dhan` returns `{valid: true}` when token is valid
- `POST /api/config/renew-token` triggers renewal and updates `token_expires_at` in DB
- `POST /api/config/test-telegram` sends a visible test message to the configured chat
