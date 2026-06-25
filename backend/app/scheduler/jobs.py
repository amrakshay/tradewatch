import logging
from zoneinfo import ZoneInfo
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

scheduler = AsyncIOScheduler(timezone=IST)

# Stored so reschedule calls can rebuild the trigger without needing all params
_alert_interval_mins: int = 30
_alert_start: str = "09:15"
_alert_end: str = "15:30"


def _get_db():
    from app.database import SessionLocal
    return SessionLocal()


def _alert_cron_trigger(interval_mins: int, start: str, end: str) -> CronTrigger:
    """
    Build a CronTrigger that fires every `interval_mins` minutes between
    `start` and `end` on weekdays only.

    Example: interval=30, start="09:15", end="15:30"
    → CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/30")
    → fires at 9:00, 9:30, 10:00 … 15:00, 15:30
    The window guard inside check_alerts trims any fire before alert_check_start.
    """
    start_h = int(start.split(":")[0])
    end_h   = int(end.split(":")[0])
    return CronTrigger(
        day_of_week="mon-fri",
        hour=f"{start_h}-{end_h}",
        minute=f"*/{interval_mins}",
        timezone=IST,
    )


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


def setup_scheduler(
    scan_time: str = "15:45",
    alert_interval_mins: int = 30,
    alert_start: str = "09:15",
    alert_end: str = "15:30",
):
    """Register all 4 jobs. Called once at application startup."""
    global _alert_interval_mins, _alert_start, _alert_end
    _alert_interval_mins = alert_interval_mins
    _alert_start = alert_start
    _alert_end = alert_end

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

    # Interval job: CronTrigger fires only during market hours on weekdays.
    # coalesce=True: if multiple runs are missed (e.g. during a scan), collapse to one.
    # misfire_grace_time=None: always run even if delayed; don't log spurious "missed" warnings.
    scheduler.add_job(
        _job_check_alerts,
        _alert_cron_trigger(alert_interval_mins, alert_start, alert_end),
        id="alert_monitor",
        kwargs={"bypass_window_guard": False},
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=None,
    )

    # Dedicated close-of-market run — bypasses window guard so it always fires
    scheduler.add_job(
        _job_check_alerts,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=IST),
        id="alert_monitor_close",
        kwargs={"bypass_window_guard": True},
        replace_existing=True,
        misfire_grace_time=120,
    )

    logger.info(
        f"Scheduler configured: scan={scan_time}, "
        f"alert every {alert_interval_mins}m between {alert_start}–{alert_end}"
    )


def reschedule_scan(new_scan_time: str):
    h, m = map(int, new_scan_time.split(":"))
    scheduler.reschedule_job(
        "daily_scan",
        trigger=CronTrigger(day_of_week="mon-fri", hour=h, minute=m, timezone=IST),
    )
    logger.info(f"daily_scan rescheduled to {new_scan_time}")


def reschedule_alert_monitor(
    new_interval_mins: int | None = None,
    new_start: str | None = None,
    new_end: str | None = None,
):
    global _alert_interval_mins, _alert_start, _alert_end
    if new_interval_mins is not None:
        _alert_interval_mins = new_interval_mins
    if new_start is not None:
        _alert_start = new_start
    if new_end is not None:
        _alert_end = new_end

    scheduler.reschedule_job(
        "alert_monitor",
        trigger=_alert_cron_trigger(_alert_interval_mins, _alert_start, _alert_end),
    )
    logger.info(
        f"alert_monitor rescheduled: every {_alert_interval_mins}m "
        f"between {_alert_start}–{_alert_end}"
    )
