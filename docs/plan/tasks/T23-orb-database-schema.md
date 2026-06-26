# T23 — ORB Database Schema

**Phase:** ORB Phase 0
**Depends on:** T02 (existing DB models)
**Blocks:** T24, T25, T27, T28

---

## Goal

Add three new database tables and two new `app_config` columns to support the ORB strategy.

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `backend/app/models/orb.py` |
| Modify | `backend/app/models/__init__.py` |
| Modify | `backend/app/models/config.py` |
| Create | `backend/alembic/versions/0002_orb_schema.py` |
| Modify | `backend/scripts/seed_db.py` |

---

## Implementation

### 1. `backend/app/models/orb.py`

```python
from sqlalchemy import Column, Integer, Real, Text
from app.database import Base

class ORBUniverse(Base):
    __tablename__ = "orb_universe"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    symbol           = Column(Text, nullable=False)
    security_id      = Column(Text, nullable=False, unique=True)
    exchange_segment = Column(Text, nullable=False, default="IDX_I")
    instrument_type  = Column(Text, nullable=False, default="INDEX")
    is_active        = Column(Integer, nullable=False, default=1)
    added_at         = Column(Text, nullable=False)


class ORBSignal(Base):
    __tablename__ = "orb_signals"

    id                        = Column(Integer, primary_key=True, autoincrement=True)
    signal_date               = Column(Text, nullable=False)
    symbol                    = Column(Text, nullable=False)
    security_id               = Column(Text, nullable=False)

    # Criterion 1
    first_candle_open         = Column(Real, nullable=False)
    first_candle_high         = Column(Real, nullable=False)
    first_candle_low          = Column(Real, nullable=False)
    first_candle_close        = Column(Real, nullable=False)
    first_candle_volume       = Column(Integer, nullable=False)
    first_candle_direction    = Column(Text, nullable=False)   # bullish | bearish
    first_candle_body_pct     = Column(Real, nullable=False)
    first_candle_volume_ratio = Column(Real, nullable=False)
    first_candle_strong       = Column(Integer, nullable=False)  # 0 | 1
    prev_day_avg_volume       = Column(Real, nullable=False)

    # Criterion 2
    orb_high                  = Column(Real, nullable=False)
    orb_low                   = Column(Real, nullable=False)

    # Criterion 3
    signal_direction          = Column(Text, nullable=False)   # LONG | SHORT
    breakout_time             = Column(Text, nullable=False)   # "HH:MM"
    breakout_candle_open      = Column(Real, nullable=False)
    breakout_candle_high      = Column(Real, nullable=False)
    breakout_candle_low       = Column(Real, nullable=False)
    breakout_candle_close     = Column(Real, nullable=False)
    breakout_candle_volume    = Column(Integer, nullable=False)
    prev_candle_volume        = Column(Integer, nullable=False)
    signal_price              = Column(Real, nullable=False)

    telegram_sent             = Column(Integer, nullable=False, default=0)
    created_at                = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("signal_date", "security_id", "signal_direction"),
    )


class IntradayCandleCache(Base):
    __tablename__ = "intraday_candle_cache"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    security_id   = Column(Text, nullable=False)
    trade_date    = Column(Text, nullable=False)   # YYYY-MM-DD
    candle_time   = Column(Text, nullable=False)   # "HH:MM" IST
    interval_mins = Column(Integer, nullable=False, default=5)
    open          = Column(Real, nullable=False)
    high          = Column(Real, nullable=False)
    low           = Column(Real, nullable=False)
    close         = Column(Real, nullable=False)
    volume        = Column(Integer, nullable=False)
    fetched_at    = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("security_id", "trade_date", "candle_time", "interval_mins"),
    )
```

### 2. Add two columns to `AppConfig` in `backend/app/models/config.py`

```python
orb_body_pct_threshold    = Column(Real, nullable=False, default=0.6)
orb_volume_ratio_threshold = Column(Real, nullable=False, default=1.5)
```

### 3. Alembic migration `0002_orb_schema.py`

```python
def upgrade():
    op.create_table("orb_universe", ...)
    op.create_table("orb_signals", ...)
    op.create_table("intraday_candle_cache", ...)
    op.add_column("app_config", sa.Column("orb_body_pct_threshold", sa.Real(), nullable=False, server_default="0.6"))
    op.add_column("app_config", sa.Column("orb_volume_ratio_threshold", sa.Real(), nullable=False, server_default="1.5"))
    # Create indexes
    op.create_index("idx_orb_signals_date",   "orb_signals", ["signal_date"])
    op.create_index("idx_orb_signals_symbol", "orb_signals", ["symbol"])
    op.create_index("idx_intraday_cache_lookup", "intraday_candle_cache",
                    ["security_id", "trade_date", "interval_mins"])

def downgrade():
    op.drop_table("intraday_candle_cache")
    op.drop_table("orb_signals")
    op.drop_table("orb_universe")
    op.drop_column("app_config", "orb_body_pct_threshold")
    op.drop_column("app_config", "orb_volume_ratio_threshold")
```

### 4. Seed default ORB universe rows in `scripts/seed_db.py`

After seeding `app_config`, also seed two default ORB instruments if `orb_universe` is empty:

```python
if db.query(ORBUniverse).count() == 0:
    db.add_all([
        ORBUniverse(symbol="NIFTY 50",  security_id="13", exchange_segment="IDX_I",
                    instrument_type="INDEX", is_active=1, added_at=now_ist()),
        ORBUniverse(symbol="BANKNIFTY", security_id="25", exchange_segment="IDX_I",
                    instrument_type="INDEX", is_active=1, added_at=now_ist()),
    ])
    db.commit()
```

---

## Run Order

```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "orb_schema"
alembic upgrade head
python scripts/seed_db.py
```

---

## Done When

- [ ] `alembic upgrade head` succeeds with no errors
- [ ] `orb_universe`, `orb_signals`, `intraday_candle_cache` tables exist in DB
- [ ] `app_config` has `orb_body_pct_threshold` and `orb_volume_ratio_threshold` columns
- [ ] `seed_db.py` inserts NIFTY 50 and BANKNIFTY rows in `orb_universe`
- [ ] Alembic `downgrade` reverses the migration cleanly
