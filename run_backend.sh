#!/usr/bin/env bash
# Run the ENTIRE agent pipeline on this machine, then leave it serving:
#
#   news agent (:8002)  ──POST /signals/ingest──▶  pipeline service (:8001)
#   sanctions monitor   ──POST /api/ingest──────▶  (ambiguity ER + investigation
#                                                   + SAR draft + SQLite sink)
#                                                          │  ckyc.db
#   Flutter dashboard  ◀──:8787──  read-API adapter  ◀─────┘
#
# One-time setup (each agent keeps its own venv):
#   python3 -m venv investigation_agent/.venv && \
#     investigation_agent/.venv/bin/pip install fastapi 'uvicorn[standard]' \
#     pydantic jellyfish python-dotenv httpx anthropic pytest
#   python3 -m venv news_agent/.venv && \
#     news_agent/.venv/bin/pip install -r news_agent/signals/requirements.txt
#
# Then:   ./run_backend.sh          (Ctrl-C stops everything)
# Dashboard: flutter run -d chrome  (in another terminal)
set -euo pipefail
cd "$(dirname "$0")"

PIPE_PORT="${PIPE_PORT:-8001}"
NEWS_PORT="${NEWS_PORT:-8002}"
READ_PORT="${READ_PORT:-8787}"
NEWS_KEY="${SIGNALS_API_KEY:-signals-dev-key-change-in-production}"

PIPE_PY="investigation_agent/.venv/bin/python"
NEWS_PY="news_agent/.venv/bin/python"
[[ -x "$PIPE_PY" ]] || { echo "missing investigation_agent/.venv — see setup in this script"; exit 1; }
[[ -x "$NEWS_PY" ]] || { echo "missing news_agent/.venv — see setup in this script"; exit 1; }

PIDS=()
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

wait_for() { # url, label
  for _ in $(seq 1 40); do
    curl -sf "$1" >/dev/null 2>&1 && { echo "  $2 is up."; return 0; }
    sleep 0.5
  done
  echo "  $2 did NOT come up — check logs"; return 1
}

# Fresh demo: the news agent dedupes articles in its own DB, and the pipeline
# rebuilds its sink on boot — wipe the news-side state so signals re-emit.
rm -f news_agent/signals/signals.db news_agent/signals_log.jsonl

echo "[1/5] pipeline service (ambiguity + investigation) on :${PIPE_PORT}"
( cd investigation_agent && exec .venv/bin/python -m uvicorn api.main:app \
    --host 127.0.0.1 --port "$PIPE_PORT" ) & PIDS+=($!)
wait_for "http://127.0.0.1:${PIPE_PORT}/health" "pipeline"

echo "[2/5] news agent on :${NEWS_PORT} (mock news, shared dataset)"
( cd news_agent && exec .venv/bin/python -m uvicorn signals.main:app \
    --host 127.0.0.1 --port "$NEWS_PORT" ) & PIDS+=($!)
wait_for "http://127.0.0.1:${NEWS_PORT}/signals/health" "news agent"

echo "[3/5] sanctions monitor -> /api/ingest (one pass over the delta stream)"
( cd Sanctions_agent && exec ../investigation_agent/.venv/bin/python \
    -m watchlist.monitor --base-url "http://127.0.0.1:${PIPE_PORT}" )

echo "[4/5] news scan -> emit -> /signals/ingest"
curl -s -X POST -H "X-API-Key: ${NEWS_KEY}" \
  "http://127.0.0.1:${NEWS_PORT}/signals/scan/trigger" >/dev/null
sleep 12   # scanner runs in a thread; give the emit cycle time to finish

echo "[5/5] read-API adapter on :${READ_PORT} (what the Flutter dashboard reads)"
python3 api/server.py --port "$READ_PORT" & PIDS+=($!)
wait_for "http://127.0.0.1:${READ_PORT}/api/health" "read-api"

echo
echo "Backend is live:"
echo "  pipeline   http://127.0.0.1:${PIPE_PORT}/docs"
echo "  news agent http://127.0.0.1:${NEWS_PORT}/docs   (scan every \$SCAN_INTERVAL_MINUTES min)"
echo "  dashboard  http://127.0.0.1:${READ_PORT}/api/alerts"
echo
echo "Now run the dashboard:  flutter run -d chrome"
echo "Ctrl-C stops all services."
wait