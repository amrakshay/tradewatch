"""
Tests for the stock universe flow (T22 § 3. Stock Universe).
Covers:
 - POST /api/stocks (custom stock)
 - GET /api/stocks
 - PATCH /api/stocks/{id}?is_active=false
 - DELETE /api/stocks/{id}
 - GET /api/stocks/universes
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.stock import Stock

IST = ZoneInfo("Asia/Kolkata")


def _seed_stock(db, symbol="RELIANCE", security_id="2885", name="Reliance Industries",
                universe_tag="NIFTY500", is_active=1):
    stock = Stock(
        symbol=symbol, security_id=security_id, name=name,
        exchange_segment="NSE_EQ", universe_tag=universe_tag,
        is_active=is_active, added_at=datetime.now(IST).isoformat(),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


# ── Add custom stock ──────────────────────────────────────────────────────────

def test_add_custom_stock(app_client):
    resp = app_client.post("/api/stocks", json={
        "symbol": "TESTCORP",
        "security_id": "99999",
        "name": "Test Corp Ltd",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "TESTCORP"
    assert data["security_id"] == "99999"
    assert data["universe_tag"] == "CUSTOM"
    assert data["is_active"] == 1


def test_add_stock_symbol_uppercased(app_client):
    resp = app_client.post("/api/stocks", json={
        "symbol": "tatapower",
        "security_id": "7777",
        "name": "Tata Power",
    })
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "TATAPOWER"


# ── List stocks ───────────────────────────────────────────────────────────────

def test_list_stocks_empty(app_client):
    resp = app_client.get("/api/stocks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_stocks_returns_active_only(app_client, db):
    _seed_stock(db, symbol="ACTIVE", security_id="111", is_active=1)
    _seed_stock(db, symbol="INACTIVE", security_id="222", is_active=0)

    resp = app_client.get("/api/stocks")
    assert resp.status_code == 200
    symbols = [s["symbol"] for s in resp.json()]
    assert "ACTIVE" in symbols
    assert "INACTIVE" not in symbols


def test_list_stocks_active_false_returns_all(app_client, db):
    _seed_stock(db, symbol="ACTIVE", security_id="111", is_active=1)
    _seed_stock(db, symbol="INACTIVE", security_id="222", is_active=0)

    resp = app_client.get("/api/stocks?active=false")
    assert resp.status_code == 200
    symbols = [s["symbol"] for s in resp.json()]
    assert "ACTIVE" in symbols
    assert "INACTIVE" in symbols


# ── Toggle (disable) stock ────────────────────────────────────────────────────

def test_disable_stock(app_client, db):
    stock = _seed_stock(db)
    resp = app_client.patch(f"/api/stocks/{stock.id}?is_active=false")
    assert resp.status_code == 200
    assert resp.json()["is_active"] == 0

    # Confirm it no longer appears in the active list
    list_resp = app_client.get("/api/stocks")
    symbols = [s["symbol"] for s in list_resp.json()]
    assert "RELIANCE" not in symbols


def test_enable_stock(app_client, db):
    stock = _seed_stock(db, is_active=0)
    resp = app_client.patch(f"/api/stocks/{stock.id}?is_active=true")
    assert resp.status_code == 200
    assert resp.json()["is_active"] == 1


def test_toggle_nonexistent_stock_404(app_client):
    resp = app_client.patch("/api/stocks/99999?is_active=false")
    assert resp.status_code == 404


# ── Delete stock ──────────────────────────────────────────────────────────────

def test_delete_stock(app_client, db):
    stock = _seed_stock(db)
    resp = app_client.delete(f"/api/stocks/{stock.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    list_resp = app_client.get("/api/stocks?active=false")
    assert all(s["id"] != stock.id for s in list_resp.json())


# ── Universe tags ─────────────────────────────────────────────────────────────

def test_universe_tags(app_client, db):
    _seed_stock(db, symbol="A", security_id="1", universe_tag="NIFTY500")
    _seed_stock(db, symbol="B", security_id="2", universe_tag="CUSTOM")

    resp = app_client.get("/api/stocks/universes")
    assert resp.status_code == 200
    tags = resp.json()
    assert "NIFTY500" in tags
    assert "CUSTOM" in tags
