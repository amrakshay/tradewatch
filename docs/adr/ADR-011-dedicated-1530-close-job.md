# ADR-011 — Dedicated 15:30 Close Job for Alert Monitor

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

The alert monitor runs on an interval (e.g. every 30 minutes) with a market hours window guard (`alert_check_start` to `alert_check_end`, default 09:15–15:30). The window guard short-circuits execution if `now` is outside the window.

**The bug**: the interval job at 15:30 compares `now` against `window_close = 15:30:00.000`. But due to scheduler overhead, `now` at execution is `15:30:00.003` — fractionally after the boundary. The comparison `now <= window_close` is `False`, so the job exits without running. The last alert check of the day is silently skipped.

## Decision

Add a **dedicated CronTrigger job** (`alert_monitor_close`) that fires at exactly 15:30 IST (Mon–Fri) and calls `check_alerts(bypass_window_guard=True)`. This job does not check the window at all — it IS the boundary.

```python
scheduler.add_job(
    lambda: asyncio.ensure_future(_job_check_alerts(bypass_window_guard=True)),
    CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=IST),
    id="alert_monitor_close",
)
```

The interval job uses a belt-and-suspenders fix: truncate `now` to the minute before comparing:
```python
if not (window_open <= now.replace(second=0, microsecond=0) <= window_close):
    return
```

## Why Two Fixes

The truncation fix alone would solve the problem for the interval job. The dedicated close job provides additional confidence: even if the interval job at 15:30 fires at 15:31 (due to a load spike), the dedicated cron job already covered the 15:30 check.

## Consequences

- Two jobs may fire close to 15:30 (the interval job and the close job). This is acceptable — they both call the same idempotent `check_alerts()` function; triggering an alert twice in quick succession is prevented by the status check (once `triggered`, it won't trigger again).
- The 5-job schedule: `token_renew`, `daily_scan`, `alert_monitor`, `alert_monitor_close` = 4 jobs.

## Root Cause Note

This is a subtle but common scheduler bug: boundary conditions with floating-point or sub-millisecond timing. The pattern of a "dedicated boundary job" is a reliable fix for this class of problem.
