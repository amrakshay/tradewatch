import logging
import asyncio
from zoneinfo import ZoneInfo
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

scheduler = AsyncIOScheduler(timezone=IST)


def _get_db():
    from app.database import SessionLocal
    return SessionLocal()


async def _job_token_renew():
    db = _get_db()
    try:
        from app.services.token_service import renew_token
        await renew_token(db)
    except Exception as e:
        logger.error(f"[scheduler] token_renew failed: {e}")
    finally:
        db.close()


async def _job_daily_scan():
    db = _get_db()
    try:
        from app.services.scanner_service import run_scan
        result = await run_scan(db)
        logger.info(f"[scheduler] daily_scan: {result['qualified']} signals on {result['scan_date']}")
    except Exception as e:
        logger.error(f"[scheduler] daily_scan failed: {e}")
    finally:
        db.close()


async def _job_check_alerts(bypass_window_guard: bool = False):
    db = _get_db()
    try:
        from app.services.alert_service import check_alerts
        await check_alerts(db, bypass_window_guard=bypass_window_guard)
    except Exception as e:
        logger.error(f"[scheduler] check_alerts failed: {e}")
    finally:
        db.close()


def setup_scheduler(scan_time: str = "15:45", alert_interval_mins: int = 30):
    """Register all 4 jobs. Called once at application startup."""
    scan_h, scan_m = map(int, scan_time.split(":"))

    scheduler.add_job(
        _job_token_renew,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=IST),
        id="token_renew",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        _job_daily_scan,
        CronTrigger(day_of_week="mon-fri", hour=scan_h, minute=scan_m, timezone=IST),
        id="daily_scan",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        lambda: asyncio.ensure_future(_job_check_alerts(bypass_window_guard=False)),
        IntervalTrigger(
            minutes=alert_interval_mins,
            start_date=datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0),
            timezone=IST,
        ),
        id="alert_monitor",
        replace_existing=True,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        lambda: asyncio.ensure_future(_job_check_alerts(bypass_window_guard=True)),
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=IST),
        id="alert_monitor_close",
        replace_existing=True,
        misfire_grace_time=120,
    )

    logger.info(f"Scheduler configured: scan={scan_time}, alert_interval={alert_interval_mins}m")


def reschedule_scan(new_scan_time: str):
    h, m = map(int, new_scan_time.split(":"))
    scheduler.reschedule_job(
        "daily_scan",
        trigger=CronTrigger(day_of_week="mon-fri", hour=h, minute=m, timezone=IST),
    )
    logger.info(f"daily_scan rescheduled to {new_scan_time}")


def reschedule_alert_monitor(new_interval_mins: int):
    scheduler.reschedule_job(
        "alert_monitor",
        trigger=IntervalTrigger(
            minutes=new_interval_mins,
            start_date=datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0),
            timezone=IST,
        ),
    )
    logger.info(f"alert_monitor rescheduled to every {new_interval_mins} minutes")
