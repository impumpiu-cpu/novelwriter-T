#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
MATURIN_VERSION="${MATURIN_VERSION:-1.9.6}"
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

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1 || ! command -v rustc >/dev/null 2>&1; then
  echo "Error: Rust toolchain not found. Install rustup/cargo first." >&2
  exit 1
fi

cd "$ROOT_DIR"
unset CONDA_PREFIX
source "$VENV_DIR/bin/activate"
uv tool run --from "maturin==${MATURIN_VERSION}" \
  maturin develop \
  --manifest-path rust/state_proto/Cargo.toml \
  --release

python - <<'PY'
import _novwr_state_proto
print(_novwr_state_proto.payload_format_version())
PY
