from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import stocks, signals, alerts, backtest

app = FastAPI(title="TradeWatch", version="0.1.0")

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
