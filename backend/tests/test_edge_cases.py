"""
Edge-case tests from T22 verification matrix.
Covers:
 - Dhan API error during scan → no signals written, no crash
 - Scanner with no active stocks → 0/0 result
 - Alert check with no active alerts → exits early, no LTP call
 - LTP not found for an alert security → warning logged, alert stays active
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.stock import Stock
from app.models.signal import ScanSignal

IST = ZoneInfo("Asia/Kolkata")


def _seed_stock(db, symbol="ERRORCO", security_id="99999"):
    db.add(Stock(
        symbol=symbol, security_id=security_id, name=f"{symbol} Ltd",
        exchange_segment="NSE_EQ", universe_tag="CUSTOM",
        is_active=1, added_at=datetime.now(IST).isoformat(),
    ))
    db.commit()


# ── Dhan API error during scan ────────────────────────────────────────────────

def test_scan_dhan_error_no_crash_no_signals(app_client, db):
    """If Dhan raises an exception, the scan should return gracefully."""
    _seed_stock(db)

    mock_dhan = MagicMock()
    mock_dhan.get_daily_ohlc = AsyncMock(side_effect=Exception("Dhan API timeout"))

    with patch("app.services.scanner_service.get_dhan_service", return_value=mock_dhan):
        resp = app_client.post("/api/scanner/run")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_scanned"] == 1
    assert data["qualified"] == 0
    assert data["skipped"] == 1
    # No signals in DB
    assert db.query(ScanSignal).count() == 0


# ── Scanner with no stocks synced ─────────────────────────────────────────────

def test_scan_before_any_stocks_synced(app_client):
    resp = app_client.post("/api/scanner/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_scanned"] == 0
    assert data["qualified"] == 0


# ── Alert check: no active alerts ────────────────────────────────────────────

def test_check_alerts_no_alerts_no_ltp_call(app_client):
    mock_dhan = MagicMock()
    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock()

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        resp = app_client.post("/api/alerts/check")

    assert resp.status_code == 200
    mock_dhan.get_ltp_batch.assert_not_called()


# ── LTP missing for a security ───────────────────────────────────────────────

def test_check_alerts_ltp_missing_for_security(app_client):
    """If LTP lookup returns no data for an alert's security, the alert stays active."""
    app_client.post("/api/alerts", json={
        "symbol": "UNKNOWN",
        "security_id": "XXXXX",
        "signal_date": "2024-01-15",
        "alert_price": 500.0,
        "valid_days": 30,
    })

    # LTP batch returns empty (security not found)
    mock_dhan = MagicMock()
    mock_dhan.get_ltp_batch.return_value = {"NSE_EQ": {}}
    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock()

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        resp = app_client.post("/api/alerts/check")

    assert resp.status_code == 200
    # Alert must remain active
    alerts = app_client.get("/api/alerts?status=active").json()
    assert len(alerts) == 1
    mock_tg.send_alert_triggered.assert_not_called()


# ── LTP batch error during alert check ───────────────────────────────────────

def test_check_alerts_ltp_fetch_error_no_crash(app_client):
    """If the LTP batch call raises, check_alerts returns gracefully (no crash)."""
    app_client.post("/api/alerts", json={
        "symbol": "RELIANCE",
        "security_id": "2885",
        "signal_date": "2024-01-15",
        "alert_price": 2400.0,
        "valid_days": 7,
    })

    mock_dhan = MagicMock()
    mock_dhan.get_ltp_batch.side_effect = Exception("LTP service unavailable")
    mock_tg = MagicMock()

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        resp = app_client.post("/api/alerts/check")

    assert resp.status_code == 200
    # Alert stays active — no state change on error
    alerts = app_client.get("/api/alerts?status=active").json()
    assert len(alerts) == 1
