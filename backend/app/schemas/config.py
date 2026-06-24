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
    dhan_access_token_masked: str
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
    dhan_access_token: Optional[str] = None  # full plaintext; ignored if masked
    telegram_bot_token: Optional[str] = None  # full plaintext
    telegram_chat_id: Optional[str] = None
