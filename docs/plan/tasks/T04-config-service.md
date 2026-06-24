# T04 — ConfigService

| Field | Value |
|-------|-------|
| Phase | 0 |
| Depends on | T02, T03 |
| Unlocks | T05, T06, T11, T15 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Implement the ConfigService that reads/writes the singleton `app_config` row. Encrypts sensitive fields on write, decrypts on read, and dispatches side effects (scheduler reschedule, service re-init) when specific fields change.

## Files to Create

- `backend/app/services/config_service.py`
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
    dhan_access_token_masked: str    # e.g. "ey...abc"
    dhan_access_token_set: bool
    token_expires_at: Optional[str]
    token_status: str
    telegram_bot_token_masked: str
    telegram_bot_token_set: bool
    telegram_chat_id: str

class ConfigUpdate(BaseModel):
    scan_time: Optional[str] = None
    scan_percentage: Optional[float] = None
    scan_days: Optional[int] = None
    alert_check_interval_mins: Optional[int] = None
    alert_check_start: Optional[str] = None
    alert_check_end: Optional[str] = None
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None   # full plaintext; ignored if starts with "ey..." masked pattern
    telegram_bot_token: Optional[str] = None  # full plaintext
    telegram_chat_id: Optional[str] = None
```

### 2. `backend/app/services/config_service.py`

```python
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.config import AppConfig
from app.services.encryption import encryption_service
from app.schemas.config import ConfigRead, ConfigUpdate

IST = ZoneInfo("Asia/Kolkata")

# Side-effect hooks — set by main.py after services are initialized
_on_scan_time_changed = None          # callable(new_scan_time: str)
_on_alert_interval_changed = None     # callable(new_interval_mins: int)
_on_dhan_credentials_changed = None   # callable()
_on_telegram_credentials_changed = None  # callable()

def register_hooks(on_scan_time, on_alert_interval, on_dhan_creds, on_telegram_creds):
    global _on_scan_time_changed, _on_alert_interval_changed
    global _on_dhan_credentials_changed, _on_telegram_credentials_changed
    _on_scan_time_changed = on_scan_time
    _on_alert_interval_changed = on_alert_interval
    _on_dhan_credentials_changed = on_dhan_creds
    _on_telegram_credentials_changed = on_telegram_creds


def get_config(db: Session) -> AppConfig:
    """Return raw ORM row (decrypted fields accessible via get_decrypted_config)."""
    return db.query(AppConfig).filter(AppConfig.id == 1).first()


def get_decrypted_config(db: Session) -> dict:
    """Return config as dict with sensitive fields fully decrypted."""
    row = get_config(db)
    return {
        "scan_time": row.scan_time,
        "scan_percentage": row.scan_percentage,
        "scan_days": row.scan_days,
        "alert_check_interval_mins": row.alert_check_interval_mins,
        "alert_check_start": row.alert_check_start,
        "alert_check_end": row.alert_check_end,
        "dhan_client_id": row.dhan_client_id,
        "dhan_access_token": encryption_service.decrypt(row.dhan_access_token),
        "token_expires_at": row.token_expires_at,
        "token_status": row.token_status,
        "telegram_bot_token": encryption_service.decrypt(row.telegram_bot_token),
        "telegram_chat_id": row.telegram_chat_id,
    }


def get_config_for_api(db: Session) -> ConfigRead:
    """Return masked config safe for API responses."""
    row = get_config(db)
    access_token_plain = encryption_service.decrypt(row.dhan_access_token)
    bot_token_plain = encryption_service.decrypt(row.telegram_bot_token)
    return ConfigRead(
        scan_time=row.scan_time,
        scan_percentage=row.scan_percentage,
        scan_days=row.scan_days,
        alert_check_interval_mins=row.alert_check_interval_mins,
        alert_check_start=row.alert_check_start,
        alert_check_end=row.alert_check_end,
        dhan_client_id=row.dhan_client_id,
        dhan_access_token_masked=encryption_service.mask(access_token_plain),
        dhan_access_token_set=encryption_service.is_set(row.dhan_access_token),
        token_expires_at=row.token_expires_at,
        token_status=row.token_status,
        telegram_bot_token_masked=encryption_service.mask(bot_token_plain),
        telegram_bot_token_set=encryption_service.is_set(row.telegram_bot_token),
        telegram_chat_id=row.telegram_chat_id,
    )


def _is_masked(value: str) -> bool:
    """True if value looks like a masked token (user didn't change it)."""
    return "..." in value and len(value) <= 10


def update_config(db: Session, update: ConfigUpdate) -> ConfigRead:
    row = get_config(db)
    old = {
        "scan_time": row.scan_time,
        "alert_check_interval_mins": row.alert_check_interval_mins,
        "dhan_access_token": row.dhan_access_token,
        "telegram_bot_token": row.telegram_bot_token,
    }

    if update.scan_time is not None:            row.scan_time = update.scan_time
    if update.scan_percentage is not None:      row.scan_percentage = update.scan_percentage
    if update.scan_days is not None:            row.scan_days = update.scan_days
    if update.alert_check_interval_mins is not None: row.alert_check_interval_mins = update.alert_check_interval_mins
    if update.alert_check_start is not None:   row.alert_check_start = update.alert_check_start
    if update.alert_check_end is not None:     row.alert_check_end = update.alert_check_end
    if update.dhan_client_id is not None:      row.dhan_client_id = update.dhan_client_id
    if update.telegram_chat_id is not None:    row.telegram_chat_id = update.telegram_chat_id

    if update.dhan_access_token and not _is_masked(update.dhan_access_token):
        row.dhan_access_token = encryption_service.encrypt(update.dhan_access_token)
        row.token_status = "unknown"   # reset; TokenService will re-check
    if update.telegram_bot_token and not _is_masked(update.telegram_bot_token):
        row.telegram_bot_token = encryption_service.encrypt(update.telegram_bot_token)

    row.updated_at = datetime.now(IST).isoformat()
    db.commit()

    # Dispatch side effects
    if update.scan_time and update.scan_time != old["scan_time"] and _on_scan_time_changed:
        _on_scan_time_changed(update.scan_time)
    if update.alert_check_interval_mins and update.alert_check_interval_mins != old["alert_check_interval_mins"] and _on_alert_interval_changed:
        _on_alert_interval_changed(update.alert_check_interval_mins)
    if update.dhan_access_token and not _is_masked(update.dhan_access_token) and _on_dhan_credentials_changed:
        _on_dhan_credentials_changed()
    if update.telegram_bot_token and not _is_masked(update.telegram_bot_token) and _on_telegram_credentials_changed:
        _on_telegram_credentials_changed()

    return get_config_for_api(db)
```

## Done When
- `get_config_for_api(db)` returns masked token values and correct `_set` booleans
- Saving a new access token encrypts it; reading back via `get_decrypted_config` returns the original value
- Saving a masked value (user didn't change the token) does not re-encrypt/overwrite the stored token
- Side effect hooks fire correctly when scheduler-related or credential fields change
