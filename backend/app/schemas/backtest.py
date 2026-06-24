from pydantic import BaseModel


class BacktestRequest(BaseModel):
    symbol: str
    security_id: str
    from_date: str          # YYYY-MM-DD
    to_date: str            # YYYY-MM-DD
    pct_threshold: float = 10.0
    num_days: int = 4


class BacktestResult(BaseModel):
    date: str
    close_price: float
    start_price: float
    return_pct: float


class BacktestResponse(BaseModel):
    symbol: str
    security_id: str
    from_date: str
    to_date: str
    pct_threshold: float
    num_days: int
    total_trading_days: int
    qualifying_days: int
    results: list[BacktestResult]
