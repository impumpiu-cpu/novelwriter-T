from __future__ import annotations

from dataclasses import dataclass

from .lifecycle import WindowIndexLifecycleSnapshot

WINDOW_INDEX_READINESS_READY = "ready"
WINDOW_INDEX_READINESS_DEGRADED = "degraded"
WINDOW_INDEX_READINESS_RETRYABLE = "retryable"


@dataclass(frozen=True, slots=True)
class WindowIndexReadinessSnapshot:
    readiness: str
    whole_book_index_available: bool
    requires_recent_fallback: bool
    retryable: bool


def resolve_window_index_readiness(
    snapshot: WindowIndexLifecycleSnapshot,
) -> WindowIndexReadinessSnapshot:
    if snapshot.status == "fresh":
        return WindowIndexReadinessSnapshot(
            readiness=WINDOW_INDEX_READINESS_READY,
            whole_book_index_available=True,
            requires_recent_fallback=False,
            retryable=False,
        )
    if snapshot.status == "failed":
        return WindowIndexReadinessSnapshot(
            readiness=WINDOW_INDEX_READINESS_RETRYABLE,
            whole_book_index_available=False,
            requires_recent_fallback=True,
            retryable=True,
        )
    return WindowIndexReadinessSnapshot(
        readiness=WINDOW_INDEX_READINESS_DEGRADED,
        whole_book_index_available=False,
        requires_recent_fallback=True,
        retryable=False,
    )


def window_index_is_ready(snapshot: WindowIndexLifecycleSnapshot) -> bool:
    return resolve_window_index_readiness(snapshot).whole_book_index_available


def window_index_requires_recent_fallback(snapshot: WindowIndexLifecycleSnapshot) -> bool:
    return resolve_window_index_readiness(snapshot).requires_recent_fallback


def window_index_is_retryable(snapshot: WindowIndexLifecycleSnapshot) -> bool:
    return resolve_window_index_readiness(snapshot).retryable
