# T14 — APScheduler Integration

| Field | Value |
|-------|-------|
| Phase | 3 |
| Depends on | T05, T10, T11, T12 |
| Unlocks | T21, T22 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Wire up APScheduler inside the FastAPI process with 4 jobs: token renewal, daily scan, alert monitor interval, and dedicated alert close job. Support runtime reschedule when config changes.

## Files to Create

- `backend/app/scheduler/jobs.py`

## Files to Modify

- `backend/app/main.py` (add scheduler startup/shutdown)

## 4 Scheduled Jobs

| Job ID | Trigger | Function | Default |
|--------|---------|----------|---------|
| `token_renew` | CronTrigger Mon-Fri 09:00 IST | `TokenService.renew_token()` | Daily |
| `daily_scan` | CronTrigger Mon-Fri 15:45 IST | `ScannerService.run_scan()` | Configurable time |
| `alert_monitor` | IntervalTrigger every 30 min | `AlertService.check_alerts()` | Configurable interval |
| `alert_monitor_close` | CronTrigger Mon-Fri 15:30 IST | `check_alerts(bypass_window_guard=True)` | Fixed |

## Steps

### 1. `backend/app/scheduler/jobs.py`

```python
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
    """
    Register all 4 jobs. Called once at application startup.
    scan_time format: "HH:MM"
    """
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

    # Dedicated close job — always fires at 15:30, bypasses the window guard
    # (the guard would short-circuit it since 15:30 is the window boundary)
    scheduler.add_job(
        lambda: asyncio.ensure_future(_job_check_alerts(bypass_window_guard=True)),
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=IST),
        id="alert_monitor_close",
        replace_existing=True,
        misfire_grace_time=120,
    )

    logger.info(f"Scheduler configured: scan={scan_time}, alert_interval={alert_interval_mins}m")


# ── Runtime reschedule (called by ConfigService side-effects) ─────────────────

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
```

### 2. Update `backend/app/main.py`

Add scheduler startup and shutdown:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.scheduler.jobs import scheduler, setup_scheduler
from app.database import SessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    db = SessionLocal()
    try:
        from app.services.config_service import get_config
        from app.services.token_service import check_token_validity

        cfg = get_config(db)
        setup_scheduler(
            scan_time=cfg.scan_time,
            alert_interval_mins=cfg.alert_check_interval_mins,
        )
        scheduler.start()

        # Check token validity on startup; renew if expiring soon
        await check_token_validity(db, startup=True)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Startup error: {e}")
    finally:
        db.close()

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)


app = FastAPI(title="TradeWatch", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Add scheduler status endpoint

```python
@app.get("/api/scheduler/status")
def scheduler_status():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
        })
    return {"running": scheduler.running, "jobs": jobs}
```

## Done When
- Backend starts and `GET /api/scheduler/status` shows 4 jobs with `next_run` values
- Changing `scan_time` via config API reschedules `daily_scan` (verify via `/api/scheduler/status`)
- At configured scan time, `daily_scan` fires and persists signals in DB
- At 15:30 IST (Mon-Fri), `alert_monitor_close` fires with `bypass_window_guard=True`
- Scheduler shuts down cleanly when FastAPI stops (no orphaned threads)
