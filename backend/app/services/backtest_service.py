import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.services.dhan_service import get_dhan_service

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

BACKTEST_BUFFER_DAYS = 14


async def run_backtest(
    db: Session,
    symbol: str,
    security_id: str,
    from_date: str,
    to_date: str,
    pct_threshold: float,
    num_days: int,
    exchange_segment: str = "NSE_EQ",
) -> dict:
    fetch_from = (date.fromisoformat(from_date) - timedelta(days=BACKTEST_BUFFER_DAYS)).isoformat()

    dhan = get_dhan_service(db)
    candles = await dhan.get_daily_ohlc(
        security_id=security_id,
        from_date=fetch_from,
        to_date=to_date,
        db=db,
        exchange_segment=exchange_segment,
    )

    results = []
    trading_days_in_range = 0

    for i in range(len(candles)):
        cdate = candles[i]["date"]
        if cdate < from_date:
            continue
        if cdate > to_date:
            break

        trading_days_in_range += 1

        if i < num_days:
            continue

        today_close = candles[i]["close"]
        start_close = candles[i - num_days]["close"]

        if start_close == 0:
            continue

        ret_pct = (today_close - start_close) / start_close * 100

        if ret_pct >= pct_threshold:
            results.append({
                "date": cdate,
                "close_price": today_close,
                "start_price": start_close,
                "return_pct": round(ret_pct, 2),
            })

    return {
        "symbol": symbol,
        "security_id": security_id,
        "from_date": from_date,
        "to_date": to_date,
        "pct_threshold": pct_threshold,
        "num_days": num_days,
        "total_trading_days": trading_days_in_range,
        "qualifying_days": len(results),
        "results": results,
    }
