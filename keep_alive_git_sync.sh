#!/bin/bash
# keep_alive_git_sync.sh
# Keeps the AI Outreach Dashboard running 24/7 and auto-pulls updates from GitHub every 60 seconds.

# Navigate to the repository directory
cd "$(dirname "$0")"

STARTUP_CMD="./startup.sh"
if [ -d ".venv" ]; then
  STARTUP_CMD="./startup_local.sh"
fi

check_port() {
  local port=$1
  timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null
  return $?
}

echo "Starting 24/7 Git Sync & Keep-Alive Daemon using $STARTUP_CMD..."
echo "Checking for updates and service status every 60 seconds."

while true; do
  # 1. Check for Git Updates
  git fetch origin main > /dev/null 2>&1
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse origin/main)

  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): New changes detected on GitHub. Pulling and restarting..."
    git pull origin main
    
    # Kill existing processes to apply update
    pkill -f "streamlit run app.py" || true
    pkill -f "uvicorn background_worker" || true
    sleep 3
    
    # Restart using detected command
    nohup $STARTUP_CMD > app.log 2>&1 &
    echo "$(date): Services restarted successfully."
  else
    # 2. Check if services are running (Streamlit: 8501, FastAPI: 8000)
    # If PORT env is set, use it for Streamlit
    STR_PORT=${PORT:-8501}
    
    if ! check_port $STR_PORT || ! check_port 8000; then
      echo "$(date): One or both services are down. Restarting..."
      pkill -f "streamlit run app.py" || true
      pkill -f "uvicorn background_worker" || true
      sleep 3
      nohup $STARTUP_CMD > app.log 2>&1 &
      echo "$(date): Services restarted."
    fi
  fi

  sleep 60
done
