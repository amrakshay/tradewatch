"""
Shared pytest fixtures for TradeWatch integration tests.

Uses an in-memory SQLite database per test, with a seeded app_config row.
DhanService and TelegramService singletons are reset before each test.
No scheduler is started — tests exercise routes and services directly.
"""
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import AppConfig, Stock, ScanSignal, Alert, AlertHistory, CandleCache  # noqa: F401 — registers models with Base
from app.routers import config, stocks, signals, alerts, backtest

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # ensures all sessions share the same in-memory connection
    )
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add(AppConfig(
        id=1,
        scan_time="15:45",
        scan_percentage=10.0,
        scan_days=4,
        alert_check_interval_mins=30,
        alert_check_start="09:15",
        alert_check_end="15:30",
        dhan_client_id="",
        dhan_access_token="",
        token_status="unknown",
        telegram_bot_token="",
        telegram_chat_id="",
        updated_at=datetime.now(IST).isoformat(),
    ))
    session.commit()

    yield session
    session.close()


@pytest.fixture
def app_client(db):
    """TestClient backed by a fresh in-memory DB. No scheduler started."""
    _app = FastAPI()

    def _override_db():
        yield db

    _app.dependency_overrides[get_db] = _override_db
    _app.include_router(config.router)
    _app.include_router(stocks.router)
    _app.include_router(signals.router)
    _app.include_router(alerts.router)
    _app.include_router(backtest.router)

    @_app.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(_app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_service_singletons():
    """Reset module-level service singletons before every test."""
    import app.services.dhan_service as dhan_mod
    import app.services.telegram_service as tg_mod
    dhan_mod._dhan_service = None
    tg_mod._telegram_service = None
    yield
    dhan_mod._dhan_service = None
    tg_mod._telegram_service = None
