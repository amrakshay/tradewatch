import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import stocks, signals, alerts, backtest
from app.scheduler.jobs import scheduler, setup_scheduler, reschedule_scan, reschedule_alert_monitor
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    db = SessionLocal()
    try:
        from app.services.config_service import get_config, register_hooks
        from app.services.token_service import startup_token_check

        cfg = get_config(db)
        setup_scheduler(
            scan_time=cfg.scan_time,
            alert_interval_mins=cfg.alert_check_interval_mins,
        )
        scheduler.start()

        register_hooks(
            on_scan_time=reschedule_scan,
            on_alert_interval=reschedule_alert_monitor,
            on_dhan_creds=lambda: None,
            on_telegram_creds=lambda: None,
        )

        await startup_token_check(db)

    except Exception as e:
        logger.error(f"Startup error: {e}")
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

app.include_router(stocks.router)
app.include_router(signals.router)
app.include_router(alerts.router)
app.include_router(backtest.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scheduler/status")
def scheduler_status():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
        })
    return {"running": scheduler.running, "jobs": jobs}
