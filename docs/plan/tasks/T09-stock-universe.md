# T09 — Stock Universe Seeding + API

| Field | Value |
|-------|-------|
| Phase | 1 |
| Depends on | T06 |
| Unlocks | T10, T17 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Build the one-time Nifty 500 seeding flow (cross-referencing Dhan master CSV with NSE's constituent list) and the stocks CRUD API endpoints.

## Files to Create

- `backend/app/services/stock_service.py`
- `backend/app/routers/stocks.py`
- `backend/app/schemas/stock.py`

## Steps

### 1. NSE Nifty 500 List

Download NSE's Nifty 500 constituent list:
- URL: `https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv`
- Relevant column: `Symbol` (e.g. `RELIANCE`)

Cross-reference with Dhan's instrument CSV (from `DhanService.download_instrument_list()`):
- Match on `symbol` → get `security_id`
- Some symbols may differ slightly (e.g. `BAJAJ-AUTO` vs `BAJAJAUT`) — handle with a normalization step: strip `-`, `&`, spaces, uppercase both sides before matching.

### 2. `backend/app/services/stock_service.py`

```python
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
    # 1. Fetch NSE Nifty 500 symbols
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(NSE_NIFTY500_URL)
        resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    nifty500_symbols = {_normalize(row["Symbol"]): row["Company Name"]
                        for row in reader if "Symbol" in row}

    # 2. Fetch Dhan instrument master
    dhan = get_dhan_service(db)
    instruments = await dhan.download_instrument_list()
    dhan_map = {_normalize(i["symbol"]): i for i in instruments}

    # 3. Cross-reference and upsert
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
```

### 3. `backend/app/schemas/stock.py`

```python
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

    class Config:
        from_attributes = True

class StockCreate(BaseModel):
    symbol: str
    security_id: str
    name: str
    exchange_segment: str = "NSE_EQ"
    universe_tag: str = "CUSTOM"
```

### 4. `backend/app/routers/stocks.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import stock_service
from app.schemas.stock import StockRead, StockCreate

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

@router.get("", response_model=list[StockRead])
def list_stocks(active: bool = True, db: Session = Depends(get_db)):
    return stock_service.get_stocks(db, active_only=active)

@router.post("", response_model=StockRead)
def add_stock(body: StockCreate, db: Session = Depends(get_db)):
    return stock_service.add_stock(db, **body.dict())

@router.patch("/{stock_id}")
def toggle_stock(stock_id: int, is_active: bool, db: Session = Depends(get_db)):
    return stock_service.toggle_stock(db, stock_id, is_active)

@router.delete("/{stock_id}")
def remove_stock(stock_id: int, db: Session = Depends(get_db)):
    stock_service.delete_stock(db, stock_id)
    return {"ok": True}

@router.post("/sync-nifty500")
async def sync_nifty500(db: Session = Depends(get_db)):
    return await stock_service.sync_nifty500(db)

@router.get("/universes")
def get_universes(db: Session = Depends(get_db)):
    from sqlalchemy import distinct
    tags = db.query(distinct(stock_service.Stock.universe_tag)).all()
    return [t[0] for t in tags]
```

### 5. Register router in `main.py`

```python
from app.routers import stocks
app.include_router(stocks.router)
```

## Done When
- `POST /api/stocks/sync-nifty500` returns `{matched: ~480, unmatched: ~20, total: 500}` (some symbols may not match due to naming differences)
- `GET /api/stocks` returns the seeded list with correct `security_id` values
- `PATCH /api/stocks/{id}?is_active=false` disables a stock; it no longer appears in active list
- `POST /api/stocks` adds a custom stock and it appears in the list
