from __future__ import annotations

from .state_proto_rust_build import (
    RUST_STATE_PROTO_BUILD_REQUEST_FORMAT_VERSION,
    RustStateProtoAssembleResult,
    RustStateProtoBuildRequest,
    RustStateProtoBuildResult,
    RustStateProtoChapter,
    RustStateProtoTarget,
    RustStateProtoUpdatePlan,
    assemble_rust_state_proto_payload,
    build_rust_state_proto_full,
    build_rust_state_proto_request,
    plan_rust_state_proto_update,
    rust_state_proto_payload_format_version,
    update_rust_state_proto_incremental,
)
from .state_proto_rust_module import (
    get_rust_state_proto_module,
    rust_state_proto_is_available,
)
from .state_proto_rust_text import (
    RustZhBlockRefinementSummary,
    RustZhCandidateCount,
    build_rust_zh_block_refinement_inputs,
    RustZhWindowSummary,
    count_rust_zh_candidates,
    summarize_rust_zh_windows,
)

# Backward-compatible alias for tests or local debugging code that monkeypatches
# the raw PyO3 module through the legacy contract module.
_novwr_state_proto = get_rust_state_proto_module()


__all__ = [
    "RUST_STATE_PROTO_BUILD_REQUEST_FORMAT_VERSION",
    "RustStateProtoAssembleResult",
    "RustStateProtoBuildRequest",
    "RustStateProtoBuildResult",
    "RustStateProtoChapter",
    "RustStateProtoTarget",
    "RustStateProtoUpdatePlan",
    "RustZhBlockRefinementSummary",
    "RustZhCandidateCount",
    "RustZhWindowSummary",
    "assemble_rust_state_proto_payload",
    "build_rust_zh_block_refinement_inputs",
    "build_rust_state_proto_full",
    "build_rust_state_proto_request",
    "count_rust_zh_candidates",
    "plan_rust_state_proto_update",
    "rust_state_proto_is_available",
    "rust_state_proto_payload_format_version",
    "summarize_rust_zh_windows",
    "update_rust_state_proto_incremental",
]
