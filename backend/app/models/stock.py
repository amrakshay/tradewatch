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
