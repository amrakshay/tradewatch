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
