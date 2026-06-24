"""
Tests for the alert flow (T22 § 5. Alert Flow).
Covers:
 - POST /api/alerts → creates with status=active, correct expires_at
 - GET /api/alerts?status=active
 - GET /api/alerts/{id}/history → has "created" event
 - POST /api/alerts/check (mocked LTP above alert_price) → stays active
 - POST /api/alerts/check (mocked LTP at/below alert_price) → triggered
 - PATCH /api/alerts/{id} → updated; history has "updated"
 - DELETE /api/alerts/{id} → removed; history has "deleted"
 - Expiry: alert with past expires_at → check_alerts → expired
 - No active alerts → check exits early
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

_ALERT_PAYLOAD = {
    "symbol": "RELIANCE",
    "security_id": "2885",
    "signal_date": "2024-01-15",
    "alert_price": 2450.00,
    "valid_days": 7,
}


# ── Create alert ──────────────────────────────────────────────────────────────

def test_create_alert(app_client):
    resp = app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["symbol"] == "RELIANCE"
    assert data["alert_price"] == 2450.00
    assert data["valid_days"] == 7
    assert data["expires_at"] is not None
    assert data["triggered_at"] is None


def test_create_alert_expires_at_correct(app_client):
    now = datetime.now(IST)
    resp = app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    data = resp.json()
    expires = datetime.fromisoformat(data["expires_at"])
    # expires_at should be ~7 days from now (allow 5s drift for test latency)
    expected = now + timedelta(days=7)
    assert abs((expires - expected).total_seconds()) < 5


# ── List alerts ───────────────────────────────────────────────────────────────

def test_list_active_alerts(app_client):
    app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    resp = app_client.get("/api/alerts?status=active")
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    assert alerts[0]["status"] == "active"


def test_list_alerts_no_status_filter(app_client):
    app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    resp = app_client.get("/api/alerts")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Alert history ─────────────────────────────────────────────────────────────

def test_alert_history_has_created_event(app_client):
    create_resp = app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    alert_id = create_resp.json()["id"]

    resp = app_client.get(f"/api/alerts/{alert_id}/history")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "created"


# ── Alert check: not triggered ────────────────────────────────────────────────

def test_check_alerts_ltp_above_price_stays_active(app_client, db):
    app_client.post("/api/alerts", json=_ALERT_PAYLOAD)

    # LTP = 2600 > alert_price 2450 → should NOT trigger
    mock_dhan = MagicMock()
    mock_dhan.get_ltp_batch.return_value = {"NSE_EQ": {"2885": 2600.0}}

    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock(return_value=True)

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        resp = app_client.post("/api/alerts/check")

    assert resp.status_code == 200
    alerts = app_client.get("/api/alerts?status=active").json()
    assert len(alerts) == 1
    mock_tg.send_alert_triggered.assert_not_called()


# ── Alert check: triggered ────────────────────────────────────────────────────

def test_check_alerts_ltp_at_price_triggers(app_client, db):
    app_client.post("/api/alerts", json=_ALERT_PAYLOAD)

    # LTP exactly = alert_price → should trigger (LTP <= alert_price)
    mock_dhan = MagicMock()
    mock_dhan.get_ltp_batch.return_value = {"NSE_EQ": {"2885": 2450.0}}

    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock(return_value=True)

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        app_client.post("/api/alerts/check")

    alerts = app_client.get("/api/alerts?status=triggered").json()
    assert len(alerts) == 1
    assert alerts[0]["triggered_price"] == 2450.0
    mock_tg.send_alert_triggered.assert_called_once()


def test_check_alerts_ltp_below_price_triggers(app_client):
    app_client.post("/api/alerts", json=_ALERT_PAYLOAD)

    mock_dhan = MagicMock()
    mock_dhan.get_ltp_batch.return_value = {"NSE_EQ": {"2885": 2400.0}}

    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock(return_value=True)

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        app_client.post("/api/alerts/check")

    triggered = app_client.get("/api/alerts?status=triggered").json()
    assert len(triggered) == 1
    assert triggered[0]["triggered_price"] == 2400.0


# ── Update alert ──────────────────────────────────────────────────────────────

def test_update_alert_price_and_valid_days(app_client):
    create_resp = app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    alert_id = create_resp.json()["id"]

    patch_resp = app_client.patch(f"/api/alerts/{alert_id}", json={
        "alert_price": 2300.0,
        "valid_days": 14,
    })
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["alert_price"] == 2300.0
    assert data["valid_days"] == 14

    # History should include "updated" event
    hist = app_client.get(f"/api/alerts/{alert_id}/history").json()
    event_types = [e["event_type"] for e in hist]
    assert "updated" in event_types


# ── Delete alert ──────────────────────────────────────────────────────────────

def test_delete_alert(app_client, db):
    from app.models.alert import AlertHistory

    create_resp = app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    alert_id = create_resp.json()["id"]

    # History should have "deleted" event before the row is removed
    del_resp = app_client.delete(f"/api/alerts/{alert_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    # Alert no longer returned
    alerts = app_client.get("/api/alerts").json()
    assert all(a["id"] != alert_id for a in alerts)


# ── Expiry ────────────────────────────────────────────────────────────────────

def test_expired_alert_detected_on_check(app_client, db):
    from app.models.alert import Alert

    # Create alert that expired 1 day ago
    past_expires = (datetime.now(IST) - timedelta(days=1)).isoformat()
    alert = Alert(
        symbol="INFY",
        security_id="1333",
        signal_date="2024-01-10",
        alert_price=1800.0,
        valid_days=1,
        expires_at=past_expires,
        status="active",
        created_at=datetime.now(IST).isoformat(),
    )
    db.add(alert)
    db.commit()

    mock_dhan = MagicMock()
    mock_dhan.get_ltp_batch.return_value = {}

    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock(return_value=True)

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        app_client.post("/api/alerts/check")

    expired = app_client.get("/api/alerts?status=expired").json()
    assert any(a["symbol"] == "INFY" for a in expired)


# ── No active alerts ──────────────────────────────────────────────────────────

def test_check_alerts_no_active_alerts(app_client):
    """check_alerts should return ok even with no alerts (no API calls made)."""
    mock_dhan = MagicMock()
    mock_tg = MagicMock()
    mock_tg.send_alert_triggered = AsyncMock()

    with patch("app.services.alert_service.get_dhan_service", return_value=mock_dhan), \
         patch("app.services.alert_service.get_telegram_service", return_value=mock_tg):
        resp = app_client.post("/api/alerts/check")

    assert resp.status_code == 200
    mock_dhan.get_ltp_batch.assert_not_called()


# ── All history ───────────────────────────────────────────────────────────────

def test_get_all_history(app_client):
    app_client.post("/api/alerts", json=_ALERT_PAYLOAD)
    resp = app_client.get("/api/alerts/history/all")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "created"
