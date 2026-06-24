"""
Tests for the scanner flow (T22 § 4. Scanner Flow).
Covers:
 - POST /scanner/run with no stocks → 0 scanned
 - POST /scanner/run with mock Dhan → signals persisted
 - Idempotency: running twice on same date doesn't duplicate signals
 - GET /signals?date= and GET /signals/dates
 - GET /signals/latest
 - Edge case: scanner with no qualifying stocks
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.stock import Stock
from app.models.signal import ScanSignal

IST = ZoneInfo("Asia/Kolkata")


def _seed_stock(db, symbol="TESTCO", security_id="11111"):
    stock = Stock(
        symbol=symbol, security_id=security_id, name=f"{symbol} Ltd",
        exchange_segment="NSE_EQ", universe_tag="CUSTOM",
        is_active=1, added_at=datetime.now(IST).isoformat(),
    )
    db.add(stock)
    db.commit()
    return stock


def _qualifying_candles():
    """9 candles where candles[-1] / candles[-5] gives >10% gain."""
    # start_price = 100, today_close = 115 → 15% gain
    return [
        {"date": f"2024-01-{i+1:02d}", "open": 99, "high": 116, "low": 98,
         "close": 100.0 if i < 5 else 115.0, "volume": 1000}
        for i in range(9)
    ]


def _non_qualifying_candles():
    """9 candles with only 2% gain — does not qualify."""
    return [
        {"date": f"2024-01-{i+1:02d}", "open": 99, "high": 103, "low": 98,
         "close": 100.0 if i < 5 else 102.0, "volume": 1000}
        for i in range(9)
    ]


# ── No stocks ─────────────────────────────────────────────────────────────────

def test_scan_no_stocks(app_client):
    resp = app_client.post("/api/scanner/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_scanned"] == 0
    assert data["qualified"] == 0
    assert data["signals"] == []


# ── With mocked Dhan ──────────────────────────────────────────────────────────

def test_scan_qualifies_signal(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        resp = app_client.post("/api/scanner/run")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_scanned"] == 1
    assert data["qualified"] == 1
    assert data["signals"][0]["symbol"] == "TESTCO"
    assert data["signals"][0]["return_pct"] == pytest.approx(15.0, rel=0.01)


def test_scan_below_threshold_no_signal(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_non_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        resp = app_client.post("/api/scanner/run")

    assert resp.status_code == 200
    data = resp.json()
    assert data["qualified"] == 0


# ── Idempotency: no duplicate signals ────────────────────────────────────────

def test_scan_twice_no_duplicate_signals(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        app_client.post("/api/scanner/run")
        app_client.post("/api/scanner/run")

    count = db.query(ScanSignal).count()
    assert count == 1  # only one signal, not two


# ── Signal retrieval ──────────────────────────────────────────────────────────

def test_get_signals_for_date(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        scan_resp = app_client.post("/api/scanner/run")

    scan_date = scan_resp.json()["scan_date"]
    resp = app_client.get(f"/api/signals?date={scan_date}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == scan_date
    assert data["count"] == 1
    assert data["signals"][0]["symbol"] == "TESTCO"


def test_get_signals_for_unknown_date(app_client):
    resp = app_client.get("/api/signals?date=1999-01-01")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
    assert resp.json()["signals"] == []


def test_get_signal_dates(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        scan_resp = app_client.post("/api/scanner/run")

    scan_date = scan_resp.json()["scan_date"]
    resp = app_client.get("/api/signals/dates")
    assert resp.status_code == 200
    assert scan_date in resp.json()


def test_get_latest_signals_empty(app_client):
    resp = app_client.get("/api/signals/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] is None
    assert data["signals"] == []


def test_get_latest_signals(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        app_client.post("/api/scanner/run")

    resp = app_client.get("/api/signals/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] is not None
    assert len(data["signals"]) == 1


# ── Scanner skips stocks with insufficient candles ────────────────────────────

def test_scan_insufficient_candles_skips(app_client, db):
    _seed_stock(db)

    # Only 2 candles — can't compute 4-day return
    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=[
        {"date": "2024-01-01", "open": 99, "high": 101, "low": 98, "close": 100.0, "volume": 1000},
        {"date": "2024-01-02", "open": 99, "high": 101, "low": 98, "close": 110.0, "volume": 1000},
    ])

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        resp = app_client.post("/api/scanner/run")

    data = resp.json()
    assert data["qualified"] == 0
    assert data["skipped"] == 1


# ── has_alert flag ────────────────────────────────────────────────────────────

def test_signal_has_alert_flag(app_client, db):
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(return_value=_qualifying_candles())

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        scan_resp = app_client.post("/api/scanner/run")

    scan_date = scan_resp.json()["scan_date"]

    # No alert yet
    resp = app_client.get(f"/api/signals?date={scan_date}")
    assert resp.json()["signals"][0]["has_alert"] is False

    # Create an alert for this security
    app_client.post("/api/alerts", json={
        "symbol": "TESTCO",
        "security_id": "11111",
        "signal_date": scan_date,
        "alert_price": 95.0,
        "valid_days": 7,
    })

    resp = app_client.get(f"/api/signals?date={scan_date}")
    assert resp.json()["signals"][0]["has_alert"] is True
