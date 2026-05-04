from __future__ import annotations

from time import perf_counter
from typing import Sequence

from app.config import Settings
from app.core.process_metrics import (
    get_process_peak_rss_kib,
    get_process_rss_kib,
)

from .builder import ChapterText
from .state_proto_model import (
    STATE_PROTO_EXECUTOR_BACKEND_NONE,
    STATE_PROTO_EXECUTOR_BACKEND_RUST,
    STATE_PROTO_EXECUTOR_STATE_FRESH,
    STATE_PROTO_EXECUTOR_STATE_MISSING,
    StateProtoBuildOutput,
    TargetSpec,
)
from .state_proto_runtime import StateProtoIndex

STATE_PROTO_RUST_REQUIRED_ERROR = (
    "Rust state-proto executor is required for state-proto index builds"
)


def execute_state_proto_build(
    *,
    chapters: Sequence[ChapterText],
    novel_language: str | None = None,
    target_specs: Sequence[TargetSpec] | None = None,
    existing_payload: bytes | None = None,
    settings: Settings | None = None,
) -> StateProtoBuildOutput:
    _ = settings
    chapter_count = len(chapters)
    chapter_chars = sum(len(getattr(chapter, "text", "") or "") for chapter in chapters)
    if not chapters:
        return StateProtoBuildOutput(
            asset_state=STATE_PROTO_EXECUTOR_STATE_MISSING,
            executor_backend=STATE_PROTO_EXECUTOR_BACKEND_NONE,
            chapter_count=chapter_count,
            chapter_chars=chapter_chars,
            rss_kib=get_process_rss_kib(),
            peak_rss_kib=get_process_peak_rss_kib(),
        )

    started_at = perf_counter()
    from .state_proto_rust_build import (
        build_rust_state_proto_full,
        build_rust_state_proto_request,
        update_rust_state_proto_incremental,
    )
    from .state_proto_rust_module import rust_state_proto_is_available

    if not rust_state_proto_is_available():
        raise RuntimeError(STATE_PROTO_RUST_REQUIRED_ERROR)

    if target_specs is None:
        resolved_target_specs = ()
        if existing_payload:
            try:
                resolved_target_specs = tuple(
                    StateProtoIndex.from_msgpack(existing_payload).targets.values()
                )
            except Exception:
                resolved_target_specs = ()
    else:
        resolved_target_specs = tuple(target_specs)
    discover_targets_ms = 0.0

    request = build_rust_state_proto_request(
        chapters=chapters,
        target_specs=resolved_target_specs,
        novel_language=novel_language,
    )
    if existing_payload:
        payload, rust_result = update_rust_state_proto_incremental(
            existing_payload=existing_payload,
            request=request,
        )
    else:
        payload, rust_result = build_rust_state_proto_full(request=request)

    target_count = rust_result.target_count
    mention_posting_count = rust_result.mention_posting_count
    coverage_rep_count = rust_result.coverage_rep_count
    payload_bytes = rust_result.payload_bytes

    return StateProtoBuildOutput(
        asset_state=STATE_PROTO_EXECUTOR_STATE_FRESH,
        executor_backend=STATE_PROTO_EXECUTOR_BACKEND_RUST,
        index_payload=payload,
        chapter_count=chapter_count,
        chapter_chars=chapter_chars,
        target_count=target_count,
        segment_count=rust_result.segment_count,
        mention_posting_count=mention_posting_count,
        claim_atom_count=rust_result.claim_atom_count,
        coverage_rep_count=coverage_rep_count,
        segmentation_ms=rust_result.segmentation_ms,
        discover_targets_ms=discover_targets_ms,
        mention_ms=rust_result.mention_ms,
        claim_ms=rust_result.claim_ms,
        coverage_ms=rust_result.coverage_ms,
        serialize_ms=rust_result.serialize_ms,
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
        payload_bytes=payload_bytes,
        rss_kib=get_process_rss_kib(),
        peak_rss_kib=get_process_peak_rss_kib(),
        plan_mode=rust_result.plan_mode,
        incremental_applied=rust_result.incremental_applied,
        rebuilt_chapter_count=rust_result.rebuilt_chapter_count,
        reused_chapter_count=rust_result.reused_chapter_count,
        fallback_reason=rust_result.fallback_reason,
    )
