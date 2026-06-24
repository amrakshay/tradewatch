from fastapi import APIRouter, Depends, HTTPException
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


@router.patch("/{stock_id}", response_model=StockRead)
def toggle_stock(stock_id: int, is_active: bool, db: Session = Depends(get_db)):
    try:
        return stock_service.toggle_stock(db, stock_id, is_active)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
