import logging
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.models.candle import CandleCache

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


def _market_closed_today() -> bool:
    """Return True if it's past 15:30 IST today (safe to cache today's candle)."""
    now = datetime.now(IST)
    close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE,
                        second=0, microsecond=0)
    return now >= close


def store_candles(db: Session, security_id: str, candles: list[dict]) -> int:
    """
    Upsert a list of candle dicts into candle_cache.
    Each dict: {date: "YYYY-MM-DD", open, high, low, close, volume}
    Skips today's candle if market is still open.
    Returns number of rows stored.
    """
    today = datetime.now(IST).strftime("%Y-%m-%d")
    stored = 0

    for c in candles:
        trade_date = c["date"]
        if trade_date == today and not _market_closed_today():
            continue   # don't cache partial intraday candle

        existing = (db.query(CandleCache)
                    .filter_by(security_id=security_id, trade_date=trade_date)
                    .first())
        if existing:
            continue   # historical data is immutable — no need to update

        db.add(CandleCache(
            security_id=security_id,
            trade_date=trade_date,
            open=c["open"],
            high=c["high"],
            low=c["low"],
            close=c["close"],
            volume=c["volume"],
            fetched_at=datetime.now(IST).isoformat(),
        ))
        stored += 1

    db.commit()
    return stored


def get_cached_candles(
    db: Session,
    security_id: str,
    from_date: str,   # YYYY-MM-DD
    to_date: str,     # YYYY-MM-DD
) -> list[dict]:
    """Return cached candles for the given security and date range."""
    rows = (db.query(CandleCache)
            .filter(
                CandleCache.security_id == security_id,
                CandleCache.trade_date >= from_date,
                CandleCache.trade_date <= to_date,
            )
            .order_by(CandleCache.trade_date)
            .all())
    return [
        {"date": r.trade_date, "open": r.open, "high": r.high,
         "low": r.low, "close": r.close, "volume": r.volume}
        for r in rows
    ]


def find_missing_ranges(
    db: Session,
    security_id: str,
    from_date: str,
    to_date: str,
) -> list[tuple[str, str]]:
    """
    Compare cached dates against the expected date range.
    Returns list of (range_start, range_end) tuples for contiguous missing gaps.

    Strategy: generate all weekday dates in [from_date, to_date],
    compare against cached set, group contiguous missing weekdays into ranges.
    Note: Dhan simply returns no data for market holidays within weekdays —
    the cache will naturally be sparse on those, which is fine.
    """
    cached_rows = (db.query(CandleCache.trade_date)
                   .filter(
                       CandleCache.security_id == security_id,
                       CandleCache.trade_date >= from_date,
                       CandleCache.trade_date <= to_date,
                   ).all())
    cached_dates = {r.trade_date for r in cached_rows}

    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)

    missing_gaps = []
    gap_start = None
    last_missing_weekday = None

    current = start
    while current <= end:
        if current.weekday() >= 5:          # weekend — skip, never a gap boundary
            current += timedelta(days=1)
            continue

        ds = current.strftime("%Y-%m-%d")
        if ds not in cached_dates:
            if gap_start is None:
                gap_start = ds
            last_missing_weekday = ds
        else:
            if gap_start is not None:       # cached weekday closes the open gap
                missing_gaps.append((gap_start, last_missing_weekday))
                gap_start = None
                last_missing_weekday = None

        current += timedelta(days=1)

    if gap_start is not None:
        missing_gaps.append((gap_start, last_missing_weekday))

    return missing_gaps
