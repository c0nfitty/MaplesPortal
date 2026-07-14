#!/QOpenSys/pkgs/bin/bash
# ---------------------------------------------------------------------------
# start.sh — Start the Maplesrugs Internal Portal on IBM i PASE
#
# Usage:
#   ./scripts/start.sh
#
# The script activates the virtual environment, exports required environment
# variables, and starts Waitress in the background.  The PID is written to
# logs/portal.pid so stop.sh can find the process.
# ---------------------------------------------------------------------------

set -euo pipefail

PORTAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PORTAL_DIR/venv"
PID_FILE="$PORTAL_DIR/logs/portal.pid"
LOG_FILE="$PORTAL_DIR/logs/portal.log"

# --- Guard: already running? ------------------------------------------------
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "Portal is already running (PID $PID). Use stop.sh first."
    exit 1
  else
    echo "Stale PID file found — removing."
    rm -f "$PID_FILE"
  fi
fi

# --- Activate virtual environment -------------------------------------------
if [ ! -d "$VENV" ]; then
  echo "ERROR: Virtual environment not found at $VENV"
  echo "       Run:  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

source "$VENV/bin/activate"

# --- Environment variables --------------------------------------------------
export PORTAL_ENV="${PORTAL_ENV:-production}"
export PORTAL_SECRET_KEY="${PORTAL_SECRET_KEY:-CHANGE_ME_IN_PRODUCTION}"
export PORTAL_REGISTRY_PATH="${PORTAL_REGISTRY_PATH:-$PORTAL_DIR/config/applications.yaml}"
export PORTAL_LOG_PATH="${PORTAL_LOG_PATH:-$PORTAL_DIR/logs/portal.log}"
export PORTAL_HEALTH_CHECK_TIMEOUT="${PORTAL_HEALTH_CHECK_TIMEOUT:-3}"

# --- Create log directory ---------------------------------------------------
mkdir -p "$PORTAL_DIR/logs"

# --- Start Waitress ---------------------------------------------------------
cd "$PORTAL_DIR"
echo "Starting portal (env=$PORTAL_ENV) on 0.0.0.0:4050..."

nohup python3 -m waitress \
  --host=0.0.0.0 \
  --port=4050 \
  --threads=4 \
  wsgi:application \
  >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Portal started. PID=$(cat $PID_FILE)  Log=$LOG_FILE"
