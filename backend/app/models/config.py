from sqlalchemy import Column, Integer, Text, Float
from app.database import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    id                        = Column(Integer, primary_key=True, default=1)
    scan_time                 = Column(Text, nullable=False, default="15:45")
    scan_percentage           = Column(Float, nullable=False, default=10.0)
    scan_days                 = Column(Integer, nullable=False, default=4)
    alert_check_interval_mins = Column(Integer, nullable=False, default=30)
    alert_check_start         = Column(Text, nullable=False, default="09:15")
    alert_check_end           = Column(Text, nullable=False, default="15:30")
    dhan_client_id            = Column(Text, nullable=False, default="")
    dhan_access_token         = Column(Text, nullable=False, default="")  # encrypted
    token_expires_at          = Column(Text, nullable=True)
    token_status              = Column(Text, nullable=False, default="unknown")
    telegram_bot_token        = Column(Text, nullable=False, default="")  # encrypted
    telegram_chat_id          = Column(Text, nullable=False, default="")
    updated_at                = Column(Text, nullable=False)
