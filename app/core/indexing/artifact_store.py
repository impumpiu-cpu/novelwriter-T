from __future__ import annotations

from typing import Any

from app.models import Novel

from app.core.derived_assets import DerivedAssetPersistResult


def persist_window_index_build_success(
    novel: Novel,
    *,
    target_revision: int,
    asset_state: str,
    index_payload: bytes | None,
    result: dict[str, Any] | None = None,
) -> DerivedAssetPersistResult:
    from .lifecycle import (
        WINDOW_INDEX_JOB_RESULT_STATE_KEY,
        WINDOW_INDEX_STATUS_MISSING,
        mark_window_index_build_succeeded,
        mark_window_index_missing,
    )

    if asset_state == WINDOW_INDEX_STATUS_MISSING:
        mark_window_index_missing(novel, revision=target_revision)
        return DerivedAssetPersistResult(
            completed_revision=target_revision,
            result={
                WINDOW_INDEX_JOB_RESULT_STATE_KEY: WINDOW_INDEX_STATUS_MISSING,
                **dict(result or {}),
            },
        )

    mark_window_index_build_succeeded(
        novel,
        index_payload=index_payload or b"",
        revision=target_revision,
    )
    return DerivedAssetPersistResult(
        completed_revision=target_revision,
        result={
            WINDOW_INDEX_JOB_RESULT_STATE_KEY: asset_state,
            **dict(result or {}),
        },
    )


def persist_window_index_build_failure(
    novel: Novel,
    *,
    target_revision: int,
    current_revision: int,
    error: str,
) -> bool:
    from .lifecycle import mark_window_index_build_failed

    if current_revision > target_revision:
        return True

    mark_window_index_build_failed(
        novel,
        error=error,
        revision=max(target_revision, current_revision, 1),
    )
    return False
