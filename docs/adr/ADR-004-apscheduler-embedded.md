# ADR-004 — APScheduler Embedded in FastAPI Process

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch has 4 scheduled jobs: token renewal (09:00), daily scan (15:45), alert monitor (every 30 min), and alert close job (15:30). These need to fire reliably Monday–Friday during market hours.

## Decision

Embed APScheduler 3.x (`AsyncIOScheduler`) directly inside the FastAPI process. Start it during the `lifespan` startup hook; shut it down during teardown.

## Rationale

- **No extra infrastructure**: no Celery worker, Redis broker, or separate cron daemon needed
- **Single process = shared state**: scheduler jobs can call service functions and DB sessions directly without IPC
- **AsyncIOScheduler**: runs jobs on the same event loop as FastAPI; `async def` jobs work natively
- **Programmatic reschedule**: `scheduler.reschedule_job()` called by ConfigService when the user changes scan time or alert interval — no restart required

## Job Definitions

| Job ID | Trigger | Notes |
|--------|---------|-------|
| `token_renew` | CronTrigger Mon-Fri 09:00 IST | Renews Dhan token daily |
| `daily_scan` | CronTrigger Mon-Fri configurable IST | Default 15:45 |
| `alert_monitor` | IntervalTrigger every N min | Configurable; has window guard |
| `alert_monitor_close` | CronTrigger Mon-Fri 15:30 IST | `bypass_window_guard=True` |

## Consequences

- If the FastAPI process crashes, scheduled jobs don't fire — operator must restart the process
- `misfire_grace_time=300` on scan/renewal jobs allows late firing if the process was temporarily paused (e.g. laptop sleep)
- No job persistence across restarts — jobs are re-registered from config on each startup

## Alternatives Considered

- **Celery + Redis**: rejected — requires two extra services; massive overkill for 4 jobs
- **System cron (crontab)**: rejected — can't share DB session or in-process services; harder to configure programmatically
- **APScheduler with SQLAlchemy job store**: considered — provides persistence across restarts; rejected as unnecessary complexity for this scale
