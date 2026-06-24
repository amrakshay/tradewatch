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
