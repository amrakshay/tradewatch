"""
Tests for the configuration flow (T22 § 2. Configuration Flow).
Covers:
 - GET /api/config returns masked tokens
 - PUT /api/config stores tokens encrypted
 - Masked-value guard: sending a masked value back doesn't overwrite the token
 - Scan-time / alert-interval updates are reflected
"""
from app.services.encryption import encryption_service


# ── GET defaults ──────────────────────────────────────────────────────────────

def test_get_config_returns_defaults(app_client):
    resp = app_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scan_time"] == "15:45"
    assert data["scan_percentage"] == 10.0
    assert data["scan_days"] == 4
    assert data["token_status"] == "unknown"
    assert data["dhan_access_token_set"] is False
    assert data["telegram_bot_token_set"] is False
    assert data["dhan_access_token_masked"] == "***"
    assert data["telegram_bot_token_masked"] == "***"


# ── PUT updates ───────────────────────────────────────────────────────────────

def test_update_scanner_settings(app_client):
    resp = app_client.put("/api/config", json={
        "scan_time": "16:00",
        "scan_percentage": 12.5,
        "scan_days": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["scan_time"] == "16:00"
    assert data["scan_percentage"] == 12.5
    assert data["scan_days"] == 5


def test_update_alert_interval(app_client):
    resp = app_client.put("/api/config", json={"alert_check_interval_mins": 15})
    assert resp.status_code == 200
    assert resp.json()["alert_check_interval_mins"] == 15


def test_update_dhan_client_id(app_client):
    resp = app_client.put("/api/config", json={"dhan_client_id": "1000000001"})
    assert resp.status_code == 200
    assert resp.json()["dhan_client_id"] == "1000000001"


def test_set_dhan_access_token_stored_encrypted(app_client, db):
    """Setting a token via PUT should store it encrypted in the DB."""
    from app.models.config import AppConfig

    plain_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_token"
    resp = app_client.put("/api/config", json={"dhan_access_token": plain_token})
    assert resp.status_code == 200

    data = resp.json()
    assert data["dhan_access_token_set"] is True
    # Masked value should not be the full token
    assert data["dhan_access_token_masked"] != plain_token
    assert "..." in data["dhan_access_token_masked"]

    # Verify the DB stores a Fernet ciphertext, not plaintext
    row = db.query(AppConfig).filter_by(id=1).first()
    db.refresh(row)
    stored = row.dhan_access_token
    assert stored != plain_token                        # not plaintext
    assert encryption_service.decrypt(stored) == plain_token  # decrypts correctly


def test_masked_value_guard_does_not_overwrite(app_client, db):
    """
    If the user sends back the masked token (didn't change it in UI),
    the stored encrypted value must NOT be overwritten.
    """
    from app.models.config import AppConfig

    plain_token = "real_secret_token_12345"
    # First: store the real token
    app_client.put("/api/config", json={"dhan_access_token": plain_token})

    # Capture the stored encrypted value
    db.expire_all()
    row = db.query(AppConfig).filter_by(id=1).first()
    encrypted_before = row.dhan_access_token
    assert encrypted_before  # must be set

    # Get the masked representation
    get_resp = app_client.get("/api/config")
    masked = get_resp.json()["dhan_access_token_masked"]

    # Send the masked value back → must NOT overwrite
    app_client.put("/api/config", json={"dhan_access_token": masked})

    db.expire_all()
    row = db.query(AppConfig).filter_by(id=1).first()
    assert row.dhan_access_token == encrypted_before  # unchanged


def test_put_no_fields_returns_400(app_client):
    resp = app_client.put("/api/config", json={})
    assert resp.status_code == 400


def test_update_telegram_settings(app_client):
    resp = app_client.put("/api/config", json={
        "telegram_chat_id": "-100123456789",
        "telegram_bot_token": "123456:ABCdefGHIjklMNOpqrSTUvwxYZ",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_chat_id"] == "-100123456789"
    assert data["telegram_bot_token_set"] is True
    assert data["telegram_bot_token_masked"] != "***"
