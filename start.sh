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
