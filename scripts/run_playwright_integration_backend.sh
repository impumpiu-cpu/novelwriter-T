#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER_PID=""

cleanup() {
  if [[ -n "$WORKER_PID" ]]; then
    kill "$WORKER_PID" >/dev/null 2>&1 || true
    wait "$WORKER_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

"$ROOT_DIR/scripts/uv_run.sh" python -m app.workers.background_jobs &
WORKER_PID="$!"

exec "$ROOT_DIR/scripts/uv_run.sh" uvicorn app.main:app --port 8000
