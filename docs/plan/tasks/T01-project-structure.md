# T01 — Project Structure & Tooling Setup

| Field | Value |
|-------|-------|
| Phase | 0 |
| Depends on | — |
| Unlocks | T02, T03, T16 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Create the complete folder skeleton, configure Python backend tooling, and scaffold the React frontend. No business logic — just the structure everything else builds on.

## Files to Create

```
tradewatch/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app entry point (skeleton)
│   │   ├── database.py        # SQLAlchemy engine + session (skeleton)
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   ├── routers/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   └── scheduler/
│   │       └── __init__.py
│   ├── alembic/
│   │   ├── env.py             # Alembic env (skeleton — populated in T02)
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── alembic.ini            # Alembic config (DB URL etc.)
│   ├── scripts/
│   │   └── seed_db.py         # Seed default config row (skeleton)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   (Vite scaffold — see steps below)
├── docs/                      # Already exists
├── start.sh
└── .gitignore                 # Already exists
```

## Steps

### 1. Backend Python environment

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
```

Create `backend/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
alembic==1.13.1
pydantic==2.7.1
pydantic-settings==2.2.1
apscheduler==3.10.4
dhanhq==2.0.1
cryptography==42.0.5
python-telegram-bot==21.3
httpx==0.27.0
pytz==2024.1
```

```bash
pip install -r requirements.txt
```

### 2. `backend/app/main.py` skeleton

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TradeWatch", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

### 3. `backend/app/database.py` skeleton

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./tradewatch.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 4. Frontend Vite scaffold

```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm install tailwindcss @tailwindcss/vite
npm install @radix-ui/react-slot class-variance-authority clsx tailwind-merge lucide-react
npm install axios @tanstack/react-query react-router-dom
npm install recharts
```

Initialize Tailwind in `vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } }
})
```

### 5. `start.sh`

```bash
#!/bin/bash
set -e

echo "Starting TradeWatch..."

# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Frontend
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID" SIGINT SIGTERM
wait
```

```bash
chmod +x start.sh
```

### 6. `backend/.env.example`

```
# Copy to .env and fill in values
DHAN_CLIENT_ID=
DHAN_ACCESS_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## Done When
- `cd backend && uvicorn app.main:app` starts without error and `GET /health` returns `{"status": "ok"}`
- `cd frontend && npm run dev` starts without error and shows default Vite page
- All directories exist as specified
