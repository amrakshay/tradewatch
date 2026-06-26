# T26 — ORB Scheduler Job

**Phase:** ORB Phase 1
**Depends on:** T14 (existing scheduler), T25 (ORBScannerService)
**Blocks:** —

---

## Goal

Add the `orb_monitor` APScheduler job to the existing scheduler setup. The job runs every 5 minutes between 9:25 AM and 3:30 PM IST on weekdays.

---

## Files to Modify

| Action | File |
|--------|------|
| Modify | `backend/app/scheduler/jobs.py` |
| Modify | `backend/app/main.py` (instantiate ORBScannerService) |

---

## Implementation

### In `backend/app/scheduler/jobs.py`

Add after existing job definitions:

```python
from app.services.orb_scanner_service import ORBScannerService

# ORB monitor: every 5 mins, anchored at 09:25 IST
# Produces ticks at 09:25, 09:30, 09:35 ... 15:25, 15:30
h_start, m_start = 9, 25
orb_start = datetime.now(IST).replace(hour=h_start, minute=m_start, second=0, microsecond=0)

scheduler.add_job(
    orb_scanner_service.run_orb_check,
    IntervalTrigger(minutes=5, start_date=orb_start, timezone=IST),
    id="orb_monitor",
    replace_existing=True,
    misfire_grace_time=60   # allow up to 60s late if system was busy
)
```

### In `backend/app/main.py`

Instantiate `ORBScannerService` alongside other services at startup:

```python
orb_scanner_service = ORBScannerService(
    dhan=dhan_service,
    telegram=telegram_service,
    config=config_service,
    db=next(get_db())   # or pass the session factory
)
```

---

## Behaviour

| Time | What happens |
|------|-------------|
| 09:25 | First tick. Fetches today's candles (only 1 candle available). Evaluates Criterion 1. Waits for range. |
| 09:30 | 2 candles. Still waiting for 3rd. |
| 09:35 | 3 candles. Range established. Starts checking breakout from candle[3:] (empty at this tick). |
| 09:40 | 4 candles. First possible breakout candle (9:35 candle) evaluated. |
| … | Each tick processes all candles accumulated so far. Already-fired signals are skipped via DB check. |
| 15:30 | Last tick. Market close. Guard returns early on any tick after 15:30. |

---

## Done When

- [ ] `orb_monitor` job appears in APScheduler job list on startup
- [ ] Job fires every 5 minutes between 09:25 and 15:30 IST on weekdays
- [ ] No job runs before 09:25 or after 15:30 (checked by internal guard in `run_orb_check`)
- [ ] No job runs on Saturday or Sunday
- [ ] If ORBScannerService raises an exception, job logs the error and reschedules normally (does not crash the scheduler)
