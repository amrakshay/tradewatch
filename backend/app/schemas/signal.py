from pydantic import BaseModel


class SignalRead(BaseModel):
    id: int
    symbol: str
    security_id: str
    close_price: float
    start_price: float
    return_pct: float
    scan_days: int
    scan_threshold: float
    has_alert: bool = False
