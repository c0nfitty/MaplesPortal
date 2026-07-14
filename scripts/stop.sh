#!/QOpenSys/pkgs/bin/bash
# ---------------------------------------------------------------------------
# stop.sh — Stop the Maplesrugs Internal Portal on IBM i PASE
# ---------------------------------------------------------------------------

set -euo pipefail

PORTAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PORTAL_DIR/logs/portal.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file found at $PID_FILE — portal may not be running."
  exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
  echo "Stopping portal (PID $PID)..."
  kill "$PID"
  sleep 2
  if kill -0 "$PID" 2>/dev/null; then
    echo "Process did not stop cleanly; sending SIGKILL..."
    kill -9 "$PID"
  fi
  rm -f "$PID_FILE"
  echo "Portal stopped."
else
  echo "Process $PID is not running. Removing stale PID file."
  rm -f "$PID_FILE"
fi
