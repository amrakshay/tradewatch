# T06 — DhanService (Base)

| Field | Value |
|-------|-------|
| Phase | 1 |
| Depends on | T04 |
| Unlocks | T08, T09 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the base DhanService wrapper around the `dhanhq` SDK. Covers OHLC fetch, LTP batch, and instrument list download. No candle caching yet (added in T08). Includes rate limit handling.

## Files to Create

- `backend/app/services/dhan_service.py`

## Rate Limits (from Dhan docs)

| API type | Limit |
|----------|-------|
| Data APIs (Historical OHLC) | 5 req/sec, 100,000/day |
| Quote APIs (LTP) | 1 req/sec, unlimited/day |

## Steps

### `backend/app/services/dhan_service.py`

```python
import asyncio
import logging
import httpx
import csv
import io
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
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

        if not data or "close" not in data:
            return []

        candles = []
        for i in range(len(data["close"])):
            ts = data["timestamp"][i]
            trade_date = datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d")
            candles.append({
                "date": trade_date,
                "open": data["open"][i],
                "high": data["high"][i],
                "low": data["low"][i],
                "close": data["close"][i],
                "volume": data["volume"][i],
            })

        return sorted(candles, key=lambda c: c["date"])

    # get_daily_ohlc() (cache-first version) is added in T08

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
```

## Done When
- `get_dhan_service(db).get_daily_ohlc_raw("2885", "2024-01-01", "2024-01-15")` returns a sorted list of candle dicts
- `get_dhan_service(db).get_ltp_batch({"NSE_EQ": [2885]})` returns `{"NSE_EQ": {"2885": <price>}}`
- `download_instrument_list()` returns a list with >450 NSE equity instruments
- Rate limit semaphore is respected (observable by running 10 concurrent calls and confirming no more than 5 run simultaneously)
- Service re-initializes cleanly when `reinit_dhan_service(db)` is called
