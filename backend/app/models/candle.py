from sqlalchemy import Column, Integer, Text, Float, UniqueConstraint
from app.database import Base


class CandleCache(Base):
    __tablename__ = "candle_cache"
    __table_args__ = (
        UniqueConstraint("security_id", "trade_date"),
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    security_id = Column(Text, nullable=False)
    trade_date  = Column(Text, nullable=False)
    open        = Column(Float, nullable=False)
    high        = Column(Float, nullable=False)
    low         = Column(Float, nullable=False)
    close       = Column(Float, nullable=False)
    volume      = Column(Integer, nullable=False)
    fetched_at  = Column(Text, nullable=False)
