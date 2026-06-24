# T02 — Database Models & Alembic Migrations

| Field | Value |
|-------|-------|
| Phase | 0 |
| Depends on | T01 |
| Unlocks | T04, T07 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Define all SQLAlchemy ORM models for the 6 database tables, configure Alembic for schema migrations, generate the initial migration, and write `scripts/seed_db.py` to seed the default `app_config` row.

## Files to Create / Modify

- `backend/app/models/config.py`
- `backend/app/models/stock.py`
- `backend/app/models/signal.py`
- `backend/app/models/alert.py`
- `backend/app/models/candle.py`
- `backend/app/models/__init__.py`
- `backend/app/database.py` (finalize)
- `backend/alembic/env.py` (configure)
- `backend/alembic.ini` (configure)
- `backend/scripts/seed_db.py`

## Steps

### 1. `backend/app/models/config.py`

```python
from sqlalchemy import Column, Integer, Text, Real
from app.database import Base

class AppConfig(Base):
    __tablename__ = "app_config"

    id                      = Column(Integer, primary_key=True, default=1)
    scan_time               = Column(Text, nullable=False, default="15:45")
    scan_percentage         = Column(Real, nullable=False, default=10.0)
    scan_days               = Column(Integer, nullable=False, default=4)
    alert_check_interval_mins = Column(Integer, nullable=False, default=30)
    alert_check_start       = Column(Text, nullable=False, default="09:15")
    alert_check_end         = Column(Text, nullable=False, default="15:30")
    dhan_client_id          = Column(Text, nullable=False, default="")
    dhan_access_token       = Column(Text, nullable=False, default="")   # encrypted
    token_expires_at        = Column(Text, nullable=True)
    token_status            = Column(Text, nullable=False, default="unknown")
    telegram_bot_token      = Column(Text, nullable=False, default="")   # encrypted
    telegram_chat_id        = Column(Text, nullable=False, default="")
    updated_at              = Column(Text, nullable=False)
```

### 2. `backend/app/models/stock.py`

```python
from sqlalchemy import Column, Integer, Text
from app.database import Base

class Stock(Base):
    __tablename__ = "stocks"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    symbol           = Column(Text, nullable=False)
    name             = Column(Text, nullable=False)
    security_id      = Column(Text, nullable=False, unique=True)
    exchange_segment = Column(Text, nullable=False, default="NSE_EQ")
    universe_tag     = Column(Text, nullable=False, default="NIFTY500")
    is_active        = Column(Integer, nullable=False, default=1)
    added_at         = Column(Text, nullable=False)
```

### 3. `backend/app/models/signal.py`

```python
from sqlalchemy import Column, Integer, Text, Real, UniqueConstraint, Index
from app.database import Base

class ScanSignal(Base):
    __tablename__ = "scan_signals"
    __table_args__ = (
        UniqueConstraint("scan_date", "security_id"),
        Index("idx_signals_date", "scan_date"),
        Index("idx_signals_symbol", "symbol"),
    )

    id             = Column(Integer, primary_key=True, autoincrement=True)
    scan_date      = Column(Text, nullable=False)
    symbol         = Column(Text, nullable=False)
    security_id    = Column(Text, nullable=False)
    close_price    = Column(Real, nullable=False)
    start_price    = Column(Real, nullable=False)
    return_pct     = Column(Real, nullable=False)
    scan_days      = Column(Integer, nullable=False)
    scan_threshold = Column(Real, nullable=False)
    created_at     = Column(Text, nullable=False)
```

### 4. `backend/app/models/alert.py`

```python
from sqlalchemy import Column, Integer, Text, Real, ForeignKey, Index
from app.database import Base

class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_symbol", "symbol"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    symbol          = Column(Text, nullable=False)
    security_id     = Column(Text, nullable=False)
    signal_date     = Column(Text, nullable=False)
    alert_price     = Column(Real, nullable=False)
    valid_days      = Column(Integer, nullable=False)
    expires_at      = Column(Text, nullable=False)
    status          = Column(Text, nullable=False, default="active")
    notes           = Column(Text, nullable=True)
    created_at      = Column(Text, nullable=False)
    triggered_at    = Column(Text, nullable=True)
    triggered_price = Column(Real, nullable=True)


class AlertHistory(Base):
    __tablename__ = "alert_history"
    __table_args__ = (
        Index("idx_history_alert_id", "alert_id"),
    )

    id         = Column(Integer, primary_key=True, autoincrement=True)
    alert_id   = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    price      = Column(Real, nullable=True)
    note       = Column(Text, nullable=True)
    timestamp  = Column(Text, nullable=False)
```

### 5. `backend/app/models/candle.py`

```python
from sqlalchemy import Column, Integer, Text, Real, UniqueConstraint
from app.database import Base

class CandleCache(Base):
    __tablename__ = "candle_cache"
    __table_args__ = (
        UniqueConstraint("security_id", "trade_date"),
        # UNIQUE implicitly creates the index — no separate CREATE INDEX needed
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    security_id = Column(Text, nullable=False)
    trade_date  = Column(Text, nullable=False)
    open        = Column(Real, nullable=False)
    high        = Column(Real, nullable=False)
    low         = Column(Real, nullable=False)
    close       = Column(Real, nullable=False)
    volume      = Column(Integer, nullable=False)
    fetched_at  = Column(Text, nullable=False)
```

### 6. `backend/app/models/__init__.py`

```python
from .config import AppConfig
from .stock import Stock
from .signal import ScanSignal
from .alert import Alert, AlertHistory
from .candle import CandleCache
```

### 7. Configure Alembic

**7a. Edit `backend/alembic.ini`**

Update the `sqlalchemy.url` line (generated by `alembic init`):

```ini
sqlalchemy.url = sqlite:///./tradewatch.db
```

**7b. Edit `backend/alembic/env.py`**

Replace the generated `target_metadata = None` section with:

```python
import sys
from pathlib import Path

# Make sure `app` package is importable from alembic/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 — import all models so Alembic sees them
from app.database import Base

# ...existing env.py boilerplate above this point...

target_metadata = Base.metadata
```

The rest of `env.py` (the `run_migrations_offline` and `run_migrations_online` functions) stays as generated by `alembic init`. No changes needed there.

**7c. Generate and apply the initial migration**

```bash
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

This creates `alembic/versions/XXXX_initial_schema.py` and applies it, creating all 6 tables in `tradewatch.db`.

> **Note:** Alembic's autogenerate may not detect all SQLite constraints perfectly. After generating, review the migration file and ensure all `UniqueConstraint` and `Index` entries are present. Add any missing ones manually before running `upgrade head`.

### 8. `backend/scripts/seed_db.py`

Seeding is now separate from migration. Run this once after `alembic upgrade head`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zoneinfo import ZoneInfo
from datetime import datetime
from app.database import SessionLocal
from app.models.config import AppConfig

IST = ZoneInfo("Asia/Kolkata")


def seed():
    db = SessionLocal()
    try:
        existing = db.query(AppConfig).filter(AppConfig.id == 1).first()
        if not existing:
            db.add(AppConfig(id=1, updated_at=datetime.now(IST).isoformat()))
            db.commit()
            print("Default config row seeded.")
        else:
            print("Config row already exists, skipping seed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
```

Run as: `python scripts/seed_db.py`

### 9. Adding future schema changes

For any schema change after the initial migration, the workflow is:
```bash
# After editing models:
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

Never modify the initial migration directly. All changes go through new migration files.

## Done When
- `alembic upgrade head` creates `tradewatch.db` with all 6 tables
- `sqlite3 tradewatch.db ".tables"` shows: `app_config stocks scan_signals alerts alert_history candle_cache alembic_version`
- `python scripts/seed_db.py` creates default config row; re-running does not duplicate
- `alembic current` shows the head revision
- `alembic history` shows one entry: `initial_schema`
