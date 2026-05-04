#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PY_BIN="$VENV_DIR/bin/python"

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is not installed." >&2
  exit 1
fi

if [[ ! -x "$PY_BIN" ]]; then
  echo "Error: project virtualenv not found at $PY_BIN" >&2
  echo "Run scripts/setup_python_env.sh first." >&2
  exit 1
fi

if [[ "$#" -eq 0 ]]; then
  echo "Usage: scripts/uv_run.sh <command> [args...]" >&2
  exit 2
fi

should_ensure_state_proto() {
  case "$1" in
    python|pytest|uvicorn)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

cd "$ROOT_DIR"
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
if [[ "${NOVWR_SKIP_STATE_PROTO_ENSURE:-0}" != "1" ]] && should_ensure_state_proto "$1"; then
  "$ROOT_DIR/scripts/ensure_state_proto_extension.sh" --quiet
fi
exec uv run --project "$ROOT_DIR" --python "$PY_BIN" --frozen "$@"
