#!/usr/bin/env bash
# jhao104/proxy_pool — Stage 1 setup script
# Run from: dev/news_pipeline/theblock/jhao104/
# Brings up Redis (Docker), creates venv, clones upstream, starts scheduler + server.
#
# Prerequisites: docker, python3.12, git
# All proxy env vars stripped from jhao104 processes — see NOTES.md §Env-Proxy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM="$SCRIPT_DIR/upstream"
VENV="$SCRIPT_DIR/venv"
PYTHON=/opt/homebrew/bin/python3.12

# ── 1. Clone upstream (skip if already present) ────────────────────────────
if [ ! -d "$UPSTREAM/.git" ]; then
  echo "[setup] Cloning jhao104/proxy_pool..."
  git -c http.sslVerify=false clone --depth 1 \
    https://github.com/jhao104/proxy_pool.git "$UPSTREAM"
else
  echo "[setup] Upstream already cloned — skipping"
fi

# ── 2. Create venv (Python 3.12) ───────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo "[setup] Creating venv with $PYTHON..."
  "$PYTHON" -m venv "$VENV"
fi

# ── 3. Install deps (relaxed pins for Python 3.12 compat) ─────────────────
# Divergences from upstream requirements.txt:
#   lxml==4.9.2      → lxml>=4.9.4   (4.9.2 fails to build: PyLong ob_digit removed in 3.12)
#   APScheduler==3.10.0 → APScheduler>=3.11.0  (3.10.0 uses pkg_resources not in 3.12 venv)
#   gunicorn==19.9.0 → gunicorn>=21.2.0  (19.9.0 uses bundled six.moves, broken on 3.12)
echo "[setup] Installing deps..."
"$VENV/bin/pip" install --quiet --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  "requests==2.31.0" \
  "lxml>=4.9.4" \
  "redis>=4.2.0" \
  "APScheduler>=3.11.0" \
  "click==8.0.1" \
  "Flask==2.1.1" \
  "werkzeug>=2.0,<2.2" \
  "gunicorn>=21.2.0"

# ── 4. Redis via Docker ────────────────────────────────────────────────────
# Default setting.py uses: redis://:pwdstring@127.0.0.1:6379/0
if docker ps --format '{{.Names}}' | grep -q '^jhao104-redis$'; then
  echo "[setup] Redis container already running"
elif docker ps -a --format '{{.Names}}' | grep -q '^jhao104-redis$'; then
  echo "[setup] Starting existing redis container..."
  docker start jhao104-redis
else
  echo "[setup] Starting Redis container..."
  docker run -d --name jhao104-redis -p 6379:6379 \
    redis:alpine redis-server --requirepass pwdstring
fi

# Wait for Redis to be ready
echo "[setup] Waiting for Redis..."
until docker exec jhao104-redis redis-cli -a pwdstring ping 2>/dev/null | grep -q PONG; do
  sleep 1
done
echo "[setup] Redis ready"

# ── 5. Start scheduler + server ───────────────────────────────────────────
# HTTP_PROXY / HTTPS_PROXY stripped so fetchers go direct (no mitmproxy dep).
# Validators use explicit proxies= arg anyway — env stripping has no effect on validation.
echo "[setup] Starting scheduler (logs → /tmp/jhao104_schedule.log)..."
cd "$UPSTREAM"
HTTP_PROXY='' HTTPS_PROXY='' "$VENV/bin/python3" proxyPool.py schedule \
  > /tmp/jhao104_schedule.log 2>&1 &
echo "  Scheduler PID: $!"

sleep 2
echo "[setup] Starting Flask server (logs → /tmp/jhao104_server.log)..."
HTTP_PROXY='' HTTPS_PROXY='' "$VENV/bin/python3" proxyPool.py server \
  > /tmp/jhao104_server.log 2>&1 &
echo "  Server PID: $!"

echo ""
echo "[setup] Done. First fetch+check cycle completes in ~2 min."
echo "  API:       http://localhost:5010/"
echo "  Count:     curl http://localhost:5010/count/"
echo "  Get proxy: curl http://localhost:5010/get/"
echo "  Logs:      tail -f /tmp/jhao104_schedule.log"
