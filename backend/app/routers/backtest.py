from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import backtest_service
from app.schemas.backtest import BacktestRequest, BacktestResponse

router = APIRouter(prefix="/api", tags=["backtest"])


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    return await backtest_service.run_backtest(
        db=db,
        symbol=body.symbol,
        security_id=body.security_id,
        from_date=body.from_date,
        to_date=body.to_date,
        pct_threshold=body.pct_threshold,
        num_days=body.num_days,
    )
