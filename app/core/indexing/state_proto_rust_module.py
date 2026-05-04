from __future__ import annotations

try:
    import _novwr_state_proto
except ImportError:  # pragma: no cover - exercised in environments without Rust build
    _novwr_state_proto = None


def get_rust_state_proto_module():
    return _novwr_state_proto


def rust_state_proto_is_available() -> bool:
    return get_rust_state_proto_module() is not None
