from pydantic import BaseModel
from typing import Optional


class StockRead(BaseModel):
    id: int
    symbol: str
    name: str
    security_id: str
    exchange_segment: str
    universe_tag: str
    is_active: bool
    data_status: Optional[str] = None
    data_error: Optional[str] = None

    class Config:
        from_attributes = True


class StockCreate(BaseModel):
    symbol: str
    security_id: str
    name: str
    exchange_segment: str = "NSE_EQ"
    universe_tag: str = "CUSTOM"
