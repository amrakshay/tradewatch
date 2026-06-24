import httpx
import logging
import csv
import io
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.stock import Stock
from app.services.dhan_service import get_dhan_service

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

NSE_NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"


def _normalize(symbol: str) -> str:
    return symbol.upper().replace("-", "").replace("&", "").replace(" ", "").replace("*", "")


async def sync_nifty500(db: Session) -> dict:
    """
    Download Nifty 500 list from NSE, cross-reference with Dhan master,
    and upsert into stocks table. Returns summary dict.
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

    matched = unmatched = 0
    for norm_sym, company_name in nifty500_symbols.items():
        dhan_row = dhan_map.get(norm_sym)
        if not dhan_row:
            logger.warning(f"No Dhan match for NSE symbol: {norm_sym}")
            unmatched += 1
            continue

        existing = db.query(Stock).filter_by(security_id=dhan_row["security_id"]).first()
        if existing:
            existing.is_active = 1
            existing.universe_tag = "NIFTY500"
        else:
            db.add(Stock(
                symbol=dhan_row["symbol"],
                name=company_name,
                security_id=dhan_row["security_id"],
                exchange_segment=dhan_row["exchange_segment"],
                universe_tag="NIFTY500",
                is_active=1,
                added_at=datetime.now(IST).isoformat(),
            ))
        matched += 1

    db.commit()
    logger.info(f"Nifty500 sync: {matched} matched, {unmatched} unmatched.")
    return {"matched": matched, "unmatched": unmatched, "total": len(nifty500_symbols)}


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


def add_stock(db: Session, symbol: str, security_id: str, name: str,
              exchange_segment: str = "NSE_EQ", universe_tag: str = "CUSTOM") -> Stock:
    stock = Stock(symbol=symbol.upper(), security_id=security_id, name=name,
                  exchange_segment=exchange_segment, universe_tag=universe_tag,
                  is_active=1, added_at=datetime.now(IST).isoformat())
    db.add(stock)
    db.commit()
    return stock


def delete_stock(db: Session, stock_id: int):
    stock = db.query(Stock).filter_by(id=stock_id).first()
    if stock:
        db.delete(stock)
        db.commit()
