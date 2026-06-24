from sqlalchemy import Column, Integer, Text, Float, ForeignKey, Index
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
    alert_price     = Column(Float, nullable=False)
    valid_days      = Column(Integer, nullable=False)
    expires_at      = Column(Text, nullable=False)
    status          = Column(Text, nullable=False, default="active")
    notes           = Column(Text, nullable=True)
    created_at      = Column(Text, nullable=False)
    triggered_at    = Column(Text, nullable=True)
    triggered_price = Column(Float, nullable=True)


class AlertHistory(Base):
    __tablename__ = "alert_history"
    __table_args__ = (
        Index("idx_history_alert_id", "alert_id"),
    )

    id         = Column(Integer, primary_key=True, autoincrement=True)
    alert_id   = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    price      = Column(Float, nullable=True)
    note       = Column(Text, nullable=True)
    timestamp  = Column(Text, nullable=False)
