#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PY_BIN="$VENV_DIR/bin/python"
CHECK_ONLY=false
QUIET=false

usage() {
  cat <<'EOF'
Usage: scripts/ensure_state_proto_extension.sh [--check-only] [--quiet]

Verifies that the required `_novwr_state_proto` extension is installed in the
repo-local virtualenv. If the extension is missing and Rust is available,
it builds the extension automatically.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --check-only)
      CHECK_ONLY=true
      ;;
    --quiet)
      QUIET=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

log() {
  if [[ "$QUIET" != "true" ]]; then
    printf '%s\n' "$1"
  fi
}

if [[ ! -x "$PY_BIN" ]]; then
  echo "Error: project virtualenv not found at $PY_BIN" >&2
  echo "Run scripts/setup_python_env.sh first." >&2
  exit 1
fi

if "$PY_BIN" -c "import _novwr_state_proto" >/dev/null 2>&1; then
  log "Rust state-proto extension is ready."
  exit 0
fi

if [[ "$CHECK_ONLY" == "true" ]]; then
  echo "Error: required _novwr_state_proto extension is missing from $VENV_DIR." >&2
  echo "Run ./scripts/build_state_proto_rust.sh after installing the Rust toolchain." >&2
  exit 1
fi

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1 || ! command -v rustc >/dev/null 2>&1; then
  echo "Error: required _novwr_state_proto extension is missing and Rust is unavailable." >&2
  echo "Install rustup/cargo first, then rerun scripts/setup_python_env.sh or ./scripts/build_state_proto_rust.sh." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/scripts/build_state_proto_rust.sh" ]]; then
  echo "Error: missing build helper at $ROOT_DIR/scripts/build_state_proto_rust.sh" >&2
  exit 1
fi

log "Building missing Rust state-proto extension..."
VENV_DIR="$VENV_DIR" "$ROOT_DIR/scripts/build_state_proto_rust.sh"

if ! "$PY_BIN" -c "import _novwr_state_proto" >/dev/null 2>&1; then
  echo "Error: state-proto build finished, but _novwr_state_proto is still unavailable." >&2
  exit 1
fi

log "Rust state-proto extension is ready."
