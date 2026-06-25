import asyncio
import httpx
import logging
import csv
import io
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.models.stock import Stock
from app.services.dhan_service import get_dhan_service, DhanNoDataError

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

NSE_NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"


def _normalize(symbol: str) -> str:
    return symbol.upper().replace("-", "").replace("&", "").replace(" ", "").replace("*", "")


def _validation_date_range() -> tuple[str, str]:
    """Return (from_date, to_date) covering the last 30 calendar days for validation."""
    today = date.today()
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


async def _validate_stock(dhan, db, stock: Stock, from_date: str, to_date: str, min_days: int):
    """
    Fetch candles for the stock and update data_status in-place.
    Uses cache so results are available for the next scan.
    """
    try:
        candles = await dhan.get_daily_ohlc(
            security_id=stock.security_id,
            from_date=from_date,
            to_date=to_date,
            db=db,
            exchange_segment=stock.exchange_segment,
        )
        if len(candles) >= min_days:
            stock.data_status = "ok"
            stock.data_error = None
        else:
            stock.data_status = "no_data"
            stock.data_error = (
                f"Only {len(candles)} trading day(s) available in last 30 days "
                f"(need at least {min_days})"
            )
    except DhanNoDataError as e:
        stock.data_status = "no_data"
        stock.data_error = str(e)


async def sync_nifty500(db: Session, min_days: int = 4) -> dict:
    """
    Download Nifty 500 list from NSE, cross-reference with Dhan master,
    upsert into stocks table, and validate newly added / previously-flagged stocks.
    Returns summary dict including list of no-data symbols.
    """
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(NSE_NIFTY500_URL)
        resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    nifty500_symbols = {_normalize(row["Symbol"]): row["Company Name"]
                        for row in reader if "Symbol" in row}

    dhan = get_dhan_service(db)
    instruments = await dhan.download_instrument_list()
    dhan_map = {_normalize(i["symbol"]): i for i in instruments}

    unmatched_symbols = []
    matched = 0
    to_validate: list[Stock] = []

    for norm_sym, company_name in nifty500_symbols.items():
        dhan_row = dhan_map.get(norm_sym)
        if not dhan_row:
            logger.warning(f"No Dhan match for NSE symbol: {norm_sym}")
            unmatched_symbols.append(norm_sym)
            continue

        existing = db.query(Stock).filter_by(security_id=dhan_row["security_id"]).first()
        if existing:
            existing.is_active = 1
            existing.universe_tag = "NIFTY500"
            # Re-validate stocks previously flagged as no_data
            if existing.data_status == "no_data":
                to_validate.append(existing)
        else:
            stock = Stock(
                symbol=dhan_row["symbol"],
                name=company_name,
                security_id=dhan_row["security_id"],
                exchange_segment=dhan_row["exchange_segment"],
                universe_tag="NIFTY500",
                is_active=1,
                added_at=datetime.now(IST).isoformat(),
            )
            db.add(stock)
            to_validate.append(stock)
        matched += 1

    db.commit()  # commit upserts so new Stock rows have IDs

    # Validate new + re-checking stocks
    from_date, to_date = _validation_date_range()
    await asyncio.gather(*[
        _validate_stock(dhan, db, s, from_date, to_date, min_days)
        for s in to_validate
    ])
    db.commit()

    no_data_symbols = [s.symbol for s in to_validate if s.data_status == "no_data"]

    logger.info(
        f"Nifty500 sync: {matched} matched, {len(unmatched_symbols)} unmatched, "
        f"{len(no_data_symbols)} no-data."
    )
    return {
        "matched": matched,
        "unmatched": len(unmatched_symbols),
        "unmatched_symbols": unmatched_symbols,
        "total": len(nifty500_symbols),
        "validated": len(to_validate),
        "no_data_count": len(no_data_symbols),
        "no_data_symbols": no_data_symbols,
    }


async def add_stock(db: Session, symbol: str, security_id: str, name: str,
                    exchange_segment: str = "NSE_EQ", universe_tag: str = "CUSTOM",
                    min_days: int = 4) -> Stock:
    existing = db.query(Stock).filter_by(security_id=security_id).first()
    if existing:
        raise ValueError(f"Stock with security_id {security_id} already exists ({existing.symbol})")

    stock = Stock(
        symbol=symbol.upper(),
        security_id=security_id,
        name=name,
        exchange_segment=exchange_segment,
        universe_tag=universe_tag,
        is_active=1,
        added_at=datetime.now(IST).isoformat(),
    )
    db.add(stock)
    db.commit()

    dhan = get_dhan_service(db)
    from_date, to_date = _validation_date_range()
    await _validate_stock(dhan, db, stock, from_date, to_date, min_days)
    db.commit()

    if stock.data_status == "no_data":
        logger.warning(f"Added stock {symbol} but it failed validation: {stock.data_error}")
    else:
        logger.info(f"Added and validated stock {symbol} ({security_id})")

    return stock


def get_stocks(db: Session, active_only: bool = True) -> list[Stock]:
    q = db.query(Stock)
    if active_only:
        q = q.filter(Stock.is_active == 1)
    return q.order_by(Stock.symbol).all()


def toggle_stock(db: Session, stock_id: int, is_active: bool) -> Stock:
    stock = db.query(Stock).filter_by(id=stock_id).first()
    if not stock:
        raise ValueError(f"Stock {stock_id} not found")
    stock.is_active = 1 if is_active else 0
    db.commit()
    return stock


def reset_stock_status(db: Session, stock_id: int) -> Stock:
    stock = db.query(Stock).filter_by(id=stock_id).first()
    if not stock:
        raise ValueError(f"Stock {stock_id} not found")
    stock.data_status = None
    stock.data_error = None
    db.commit()
    return stock


def delete_stock(db: Session, stock_id: int):
    stock = db.query(Stock).filter_by(id=stock_id).first()
    if stock:
        db.delete(stock)
        db.commit()
