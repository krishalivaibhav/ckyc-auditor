#!/usr/bin/env bash
# Seed ckyc.db (if needed) and serve the local read API for the Flutter dashboard.
# Single device: run this, then `flutter run` in another terminal.
#
#   ./run_backend.sh            # seed + serve on 127.0.0.1:8787
#   ./run_backend.sh --no-seed  # serve without reseeding (keep current data)
#   PORT=9000 ./run_backend.sh  # different port (also pass --dart-define=API_BASE_URL)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8787}"
if [[ "${1:-}" != "--no-seed" ]]; then
  echo "Seeding ckyc.db..."
  python3 db/seed.py
fi
echo "Starting read API on http://127.0.0.1:${PORT}"
exec python3 api/server.py --port "${PORT}"
