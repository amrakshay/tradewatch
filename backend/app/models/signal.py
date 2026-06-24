from sqlalchemy import Column, Integer, Text, Float, UniqueConstraint, Index
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
    close_price    = Column(Float, nullable=False)
    start_price    = Column(Float, nullable=False)
    return_pct     = Column(Float, nullable=False)
    scan_days      = Column(Integer, nullable=False)
    scan_threshold = Column(Float, nullable=False)
    created_at     = Column(Text, nullable=False)
