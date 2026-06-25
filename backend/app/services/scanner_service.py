import asyncio
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.models.signal import ScanSignal
from app.models.stock import Stock
from sqlalchemy import or_
from app.services.dhan_service import get_dhan_service, DhanNoDataError
from app.services.config_service import get_decrypted_config

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Module-level progress state — updated live during a scan
_progress: dict = {
    "status": "idle",       # idle | running | completed | failed
    "total": 0,
    "completed": 0,
    "signals_found": 0,
    "scan_date": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def get_scan_progress() -> dict:
    return dict(_progress)


async def run_scan(db: Session, scan_date: date | None = None) -> dict:
    """
    Scan all active stocks for the given date (defaults to today IST).
    Returns summary: {scan_date, total_scanned, qualified, skipped, signals: [...]}
    """
    global _progress
    _progress.update({
        "status": "running",
        "total": 0,
        "completed": 0,
        "signals_found": 0,
        "scan_date": None,
        "started_at": datetime.now(IST).isoformat(),
        "finished_at": None,
        "error": None,
    })

    try:
        cfg = get_decrypted_config(db)
        scan_date = scan_date or datetime.now(IST).date()
        scan_date_str = scan_date.strftime("%Y-%m-%d")
        threshold = cfg["scan_percentage"]
        num_days = cfg["scan_days"]

        from_date = (scan_date - timedelta(days=14)).strftime("%Y-%m-%d")
        to_date = scan_date_str

        stocks = db.query(Stock).filter(
            Stock.is_active == 1,
            or_(Stock.data_status.is_(None), Stock.data_status != "no_data"),
        ).all()
        dhan = get_dhan_service(db)

        _progress["total"] = len(stocks)
        _progress["scan_date"] = scan_date_str

        qualified = []
        skipped = 0

        async def process_stock(stock: Stock):
            nonlocal skipped
            try:
                candles = await dhan.get_daily_ohlc(
                    security_id=stock.security_id,
                    from_date=from_date,
                    to_date=to_date,
                    db=db,
                    exchange_segment=stock.exchange_segment,
                )

                candles = [c for c in candles if c["date"] <= scan_date_str]

                if len(candles) < num_days + 1:
                    logger.debug(f"{stock.symbol}: insufficient candles ({len(candles)}), skipping.")
                    skipped += 1
                    return

                today_close = candles[-1]["close"]
                start_close = candles[-(num_days + 1)]["close"]

                if start_close == 0:
                    skipped += 1
                    return

                ret_pct = (today_close - start_close) / start_close * 100

                if ret_pct >= threshold:
                    qualified.append({
                        "symbol": stock.symbol,
                        "security_id": stock.security_id,
                        "close_price": today_close,
                        "start_price": start_close,
                        "return_pct": round(ret_pct, 2),
                    })
                    _progress["signals_found"] = len(qualified)

                # Clear any previous no_data flag if data came through fine
                if stock.data_status == "no_data":
                    stock.data_status = None
                    stock.data_error = None

            except DhanNoDataError as e:
                logger.debug(f"{stock.symbol}: marking as no_data — {e}")
                stock.data_status = "no_data"
                stock.data_error = str(e)
                skipped += 1
            except Exception as e:
                logger.error(f"Error scanning {stock.symbol}: {e}")
                skipped += 1
            finally:
                _progress["completed"] += 1

        await asyncio.gather(*[process_stock(s) for s in stocks])

        db.commit()  # persist data_status / data_error updates from process_stock
        _persist_signals(db, scan_date_str, qualified, num_days, threshold)

        _progress.update({
            "status": "completed",
            "finished_at": datetime.now(IST).isoformat(),
        })

        return {
            "scan_date": scan_date_str,
            "total_scanned": len(stocks),
            "qualified": len(qualified),
            "skipped": skipped,
            "signals": qualified,
        }

    except Exception as e:
        _progress.update({
            "status": "failed",
            "finished_at": datetime.now(IST).isoformat(),
            "error": str(e),
        })
        raise


def _persist_signals(db: Session, scan_date: str, signals: list[dict],
                     scan_days: int, scan_threshold: float):
    """Upsert scan signals. Skips if no signals (market holiday detection)."""
    if not signals:
        logger.info(f"No signals for {scan_date} — possible market holiday or no qualifying stocks.")
        return

    for s in signals:
        existing = (db.query(ScanSignal)
                    .filter_by(scan_date=scan_date, security_id=s["security_id"])
                    .first())
        if existing:
            continue
        db.add(ScanSignal(
            scan_date=scan_date,
            symbol=s["symbol"],
            security_id=s["security_id"],
            close_price=s["close_price"],
            start_price=s["start_price"],
            return_pct=s["return_pct"],
            scan_days=scan_days,
            scan_threshold=scan_threshold,
            created_at=datetime.now(IST).isoformat(),
        ))
    db.commit()
    logger.info(f"Scan {scan_date}: {len(signals)} signals persisted.")


def get_signals_for_date(db: Session, scan_date: str, alert_security_ids: set = None) -> list:
    rows = (db.query(ScanSignal)
            .filter(ScanSignal.scan_date == scan_date)
            .order_by(ScanSignal.return_pct.desc())
            .all())
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "symbol": r.symbol,
            "security_id": r.security_id,
            "scan_date": r.scan_date,
            "close_price": r.close_price,
            "start_price": r.start_price,
            "return_pct": r.return_pct,
            "scan_days": r.scan_days,
            "scan_threshold": r.scan_threshold,
            "has_alert": r.security_id in (alert_security_ids or set()),
        })
    return result


def get_signal_dates(db: Session) -> list[str]:
    from sqlalchemy import distinct
    rows = db.query(distinct(ScanSignal.scan_date)).order_by(ScanSignal.scan_date.desc()).all()
    return [r[0] for r in rows]
