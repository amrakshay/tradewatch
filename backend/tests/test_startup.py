"""
Tests for basic startup flows: health check, DB connectivity.
"""


def test_health(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_config_defaults(app_client):
    """GET /api/config returns the seeded defaults."""
    resp = app_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scan_time"] == "15:45"
    assert data["scan_percentage"] == 10.0
    assert data["scan_days"] == 4
    assert data["alert_check_interval_mins"] == 30
    assert data["dhan_access_token_set"] is False
    assert data["telegram_bot_token_set"] is False
