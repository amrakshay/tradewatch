import asyncio
import logging
import httpx
import csv
import io
from zoneinfo import ZoneInfo
from datetime import datetime
from dhanhq import dhanhq
from app.services.config_service import get_decrypted_config

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

DHAN_INSTRUMENT_CSV_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

# Semaphore: max 5 concurrent historical data requests (Dhan rate limit)
_historical_semaphore = asyncio.Semaphore(5)


class DhanService:
    def __init__(self, client_id: str, access_token: str):
        self._client_id = client_id
        self._access_token = access_token
        self._dhan = dhanhq(client_id, access_token)

    def reinit(self, client_id: str, access_token: str):
        """Re-initialize with new credentials (called by ConfigService hook)."""
        self._client_id = client_id
        self._access_token = access_token
        self._dhan = dhanhq(client_id, access_token)

    # ── Historical OHLC ──────────────────────────────────────────────────────

    async def get_daily_ohlc_raw(
        self,
        security_id: str,
        from_date: str,   # YYYY-MM-DD
        to_date: str,     # YYYY-MM-DD
        exchange_segment: str = "NSE_EQ",
    ) -> list[dict]:
        """
        Fetch daily candles from Dhan API (no caching).
        Returns list of {date, open, high, low, close, volume}.
        """
        async with _historical_semaphore:
            try:
                data = self._dhan.historical_daily_data(
                    security_id=security_id,
                    exchange_segment=exchange_segment,
                    instrument_type="EQUITY",
                    from_date=from_date,
                    to_date=to_date,
                    expiry_code=0,
                )
            except Exception as e:
                logger.error(f"Dhan OHLC fetch failed for {security_id}: {e}")
                raise

        # dhanhq v2 wraps the response: {"status": ..., "remarks": ..., "data": {ohlcv}}
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
        else:
            inner = data

        if not inner or "close" not in inner:
            logger.warning("Dhan OHLC: unexpected response for %s: %s", security_id, data)
            return []

        candles = []
        for i in range(len(inner["close"])):
            ts = inner["timestamp"][i]
            if ts > 1e10:  # milliseconds guard (currently seconds, but be safe)
                ts = ts / 1000
            trade_date = datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d")
            candles.append({
                "date": trade_date,
                "open": inner["open"][i],
                "high": inner["high"][i],
                "low": inner["low"][i],
                "close": inner["close"][i],
                "volume": inner["volume"][i],
            })

        return sorted(candles, key=lambda c: c["date"])

    async def get_daily_ohlc(
        self,
        security_id: str,
        from_date: str,         # YYYY-MM-DD
        to_date: str,           # YYYY-MM-DD
        db=None,
        exchange_segment: str = "NSE_EQ",
    ) -> list[dict]:
        """
        Cache-first daily OHLC fetch.
        1. Get cached candles for the range.
        2. Find missing date gaps.
        3. Fetch only missing ranges from Dhan API.
        4. Store newly fetched candles in cache.
        5. Merge and return sorted list.
        """
        if db is None:
            return await self.get_daily_ohlc_raw(security_id, from_date, to_date, exchange_segment)

        from app.services.candle_cache import (
            get_cached_candles, find_missing_ranges, store_candles
        )

        cached = get_cached_candles(db, security_id, from_date, to_date)
        missing_ranges = find_missing_ranges(db, security_id, from_date, to_date)

        if not missing_ranges:
            logger.debug(f"Cache hit: {security_id} {from_date}→{to_date}")
            return cached

        new_candles = []
        for gap_start, gap_end in missing_ranges:
            logger.debug(f"Cache miss: fetching {security_id} {gap_start}→{gap_end}")
            fetched = await self.get_daily_ohlc_raw(
                security_id, gap_start, gap_end, exchange_segment
            )
            store_candles(db, security_id, fetched)
            new_candles.extend(fetched)

        all_candles = {c["date"]: c for c in cached}
        all_candles.update({c["date"]: c for c in new_candles})
        return sorted(all_candles.values(), key=lambda c: c["date"])

    # ── LTP Batch ────────────────────────────────────────────────────────────

    def get_ltp_batch(self, securities: dict) -> dict:
        """
        Fetch LTP for up to 1000 instruments.
        securities: {"NSE_EQ": [2885, 1333, ...]}
        Returns: {"NSE_EQ": {"2885": 2441.50, ...}}
        """
        try:
            resp = self._dhan.ltp(securities)
            result = {}
            for segment, items in resp.get("data", {}).items():
                result[segment] = {
                    sid: info["last_price"]
                    for sid, info in items.items()
                }
            return result
        except Exception as e:
            logger.error(f"LTP batch fetch failed: {e}")
            raise

    # ── Instrument Master ────────────────────────────────────────────────────

    async def download_instrument_list(self) -> list[dict]:
        """
        Download Dhan's master instrument CSV and return NSE equity rows.
        Returns list of {symbol, security_id, name, exchange_segment}.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(DHAN_INSTRUMENT_CSV_URL)
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        instruments = []
        for row in reader:
            if (row.get("SEM_EXM_EXCH_ID") == "NSE"
                    and row.get("SEM_INSTRUMENT_NAME") == "EQUITY"):
                instruments.append({
                    "symbol": row["SEM_TRADING_SYMBOL"],
                    "security_id": row["SEM_SMST_SECURITY_ID"],
                    "name": row.get("SM_SYMBOL_NAME", row["SEM_TRADING_SYMBOL"]),
                    "exchange_segment": "NSE_EQ",
                })
        return instruments


# Module-level singleton — initialized lazily from config
_dhan_service: DhanService | None = None


def get_dhan_service(db=None) -> DhanService:
    global _dhan_service
    if _dhan_service is None:
        if db is None:
            raise RuntimeError("DhanService not initialized and no db provided.")
        from app.database import SessionLocal
        _db = db or SessionLocal()
        cfg = get_decrypted_config(_db)
        _dhan_service = DhanService(cfg["dhan_client_id"], cfg["dhan_access_token"])
    return _dhan_service


def reinit_dhan_service(db):
    """Called by ConfigService hook when credentials change."""
    global _dhan_service
    cfg = get_decrypted_config(db)
    if _dhan_service:
        _dhan_service.reinit(cfg["dhan_client_id"], cfg["dhan_access_token"])
    else:
        _dhan_service = DhanService(cfg["dhan_client_id"], cfg["dhan_access_token"])
