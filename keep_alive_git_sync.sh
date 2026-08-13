#!/bin/bash
# keep_alive_git_sync.sh
# Test sync hook - 24/7 keep-alive check
# Keeps the AI Outreach Dashboard running 24/7 in Docker and auto-pulls updates from GitHub every 60 seconds.

# Navigate to the repository directory
cd "$(dirname "$0")"

echo "Starting 24/7 Git Sync & Keep-Alive Daemon (Docker Mode)..."
echo "Checking for GitHub updates and Docker container status every 60 seconds."

while true; do
  # 1. Check for Git Updates
  git fetch origin main > /dev/null 2>&1
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse origin/main)

  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): New changes detected on GitHub. Pulling and rebuilding Docker container..."
    git pull origin main
    
    # Rebuild and recreate container
    docker build -t outreach-app .
    docker stop outreach || true
    docker rm outreach || true
    docker run -d --name outreach --restart always -p 8000:8000 -p 8501:8501 outreach-app
    echo "$(date): Docker container rebuilt and restarted."
  else
    # 2. Check if Docker container is running, if not restart/run it
    if ! docker ps | grep -q "outreach"; then
      echo "$(date): outreach container is down. Restarting..."
      docker start outreach || (docker rm outreach || true; docker run -d --name outreach --restart always -p 8000:8000 -p 8501:8501 outreach-app)
    fi
  fi

  sleep 60
done
