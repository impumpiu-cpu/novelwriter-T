from __future__ import annotations

from app.core.indexing.status import (
    WINDOW_INDEX_READINESS_DEGRADED,
    WINDOW_INDEX_READINESS_READY,
    WINDOW_INDEX_READINESS_RETRYABLE,
    resolve_window_index_readiness,
    window_index_is_ready,
    window_index_is_retryable,
    window_index_requires_recent_fallback,
)


class _Snapshot:
    def __init__(self, status: str) -> None:
        self.status = status


def test_resolve_window_index_readiness_marks_fresh_as_ready():
    snapshot = resolve_window_index_readiness(_Snapshot("fresh"))

    assert snapshot.readiness == WINDOW_INDEX_READINESS_READY
    assert snapshot.whole_book_index_available is True
    assert snapshot.requires_recent_fallback is False
    assert snapshot.retryable is False
    assert window_index_is_ready(_Snapshot("fresh")) is True


def test_resolve_window_index_readiness_marks_failed_as_retryable():
    snapshot = resolve_window_index_readiness(_Snapshot("failed"))

    assert snapshot.readiness == WINDOW_INDEX_READINESS_RETRYABLE
    assert snapshot.whole_book_index_available is False
    assert snapshot.requires_recent_fallback is True
    assert snapshot.retryable is True
    assert window_index_is_retryable(_Snapshot("failed")) is True


def test_resolve_window_index_readiness_marks_stale_like_states_as_degraded():
    for raw_status in ("missing", "stale"):
        snapshot = resolve_window_index_readiness(_Snapshot(raw_status))

        assert snapshot.readiness == WINDOW_INDEX_READINESS_DEGRADED
        assert snapshot.whole_book_index_available is False
        assert snapshot.requires_recent_fallback is True
        assert snapshot.retryable is False
        assert window_index_requires_recent_fallback(_Snapshot(raw_status)) is True
