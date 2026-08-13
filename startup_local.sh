#!/bin/bash
set -e

echo "=== Starting AI Outreach Dashboard (Local) ==="

# Activate virtual environment
source .venv/bin/activate

# Start the background worker (FastAPI + APScheduler) on port 8000
echo "[1/2] Starting background worker on port 8000..."
uvicorn background_worker:app --host 0.0.0.0 --port 8000 &
WORKER_PID=$!

# Small delay so worker is up before Streamlit starts
sleep 2

# Start Streamlit on port 8501
echo "[2/2] Starting Streamlit on port 8501..."
streamlit run app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false &
STREAMLIT_PID=$!

echo "=== Both services started ==="
echo "  Background Worker PID: $WORKER_PID (port 8000)"
echo "  Streamlit PID:         $STREAMLIT_PID (port 8501)"

# Wait for processes
wait $WORKER_PID $STREAMLIT_PID
EXIT_CODE=$?

echo "=== A process exited with code $EXIT_CODE. Shutting down. ==="
kill $WORKER_PID $STREAMLIT_PID 2>/dev/null || true
exit $EXIT_CODE
