"""Rust-only state-proto runtime query coverage."""

from __future__ import annotations

import pytest

from benchmarks.state_index_v1 import build_state_proto_reference_cases

from app.core.indexing import (
    CUE_ASSERTED,
    CUE_HISTORICAL,
    CUE_HYPOTHETICAL,
    CUE_NEGATED,
    SLOT_ENTITY_CURRENT_LOCATION,
    STATE_PROTO_EXECUTOR_BACKEND_RUST,
    StateProtoIndex,
    SUPPORTED_CLAIM_SLOTS,
    TargetSpec,
    execute_state_proto_build,
)
from app.core.indexing.window_index import NovelIndex
from app.core.indexing.builder import ChapterText
from app.core.indexing.state_proto import (
    DEFAULT_CJK_OPEN_CHARS,
    DEFAULT_CJK_PREVIEW_CHARS,
    DEFAULT_NON_CJK_OPEN_CHARS,
    DEFAULT_NON_CJK_PREVIEW_CHARS,
    _detect_script_mode,
)
from app.core.indexing.state_proto_rust_contract import rust_state_proto_is_available

pytestmark = pytest.mark.skipif(
    not rust_state_proto_is_available(),
    reason="Rust state-proto module unavailable",
)


def _build_output(
    chapters: tuple[str, ...],
    *,
    target_specs: tuple[TargetSpec, ...] | None,
    novel_language: str,
):
    chapter_rows = [
        ChapterText(chapter_id=index, text=text)
        for index, text in enumerate(chapters, start=1)
    ]
    output = execute_state_proto_build(
        chapters=chapter_rows,
        novel_language=novel_language,
        target_specs=target_specs,
    )
    assert output.executor_backend == STATE_PROTO_EXECUTOR_BACKEND_RUST
    return output


def _build_index(
    chapters: tuple[str, ...],
    *,
    target_specs: tuple[TargetSpec, ...],
    novel_language: str = "zh",
) -> StateProtoIndex:
    output = _build_output(
        chapters,
        target_specs=target_specs,
        novel_language=novel_language,
    )
    return StateProtoIndex.from_msgpack(output.index_payload)


@pytest.mark.parametrize(
    ("text", "expected_mode"),
    [
        (
            "林秋在云港旧街盘货。顾衡在旁边记账。\n\n苏禾从桥头走来，带着新的消息。" * 24,
            "cjk_heavy",
        ),
        (
            "Marcus waits in the archive hall. Elise checks the west gate. "
            "They keep moving between the stone bridge and the records room.\n\n" * 18,
            "space_delimited",
        ),
    ],
)
def test_execute_state_proto_build_segments_long_chapters_for_cjk_and_space_delimited_text(
    text: str,
    expected_mode: str,
):
    assert _detect_script_mode(text) == expected_mode

    output = _build_output(
        (text,),
        target_specs=(TargetSpec(id="focus", canonical_name="林秋" if expected_mode == "cjk_heavy" else "Marcus"),),
        novel_language="zh" if expected_mode == "cjk_heavy" else "en",
    )
    index = StateProtoIndex.from_msgpack(output.index_payload)

    assert len(index.segments) >= 2
    for segment in index.segments:
        assert 0 <= segment.start_pos < segment.end_pos <= len(text)
        assert segment.end_pos - segment.start_pos <= 820


def test_closed_slot_registry_only_emits_supported_slots():
    index = _build_index(
        ("林秋加入云港会。林秋成为信使。林秋还活着。林秋喜欢蓝袍。",),
        target_specs=(TargetSpec(id="lin_qiu", canonical_name="林秋"),),
    )

    emitted_slots = {claim.key.slot for claim in index.claim_atoms}

    assert emitted_slots <= SUPPORTED_CLAIM_SLOTS
    assert emitted_slots == {
        "entity.current_affiliation",
        "entity.current_role",
        "entity.life_state",
    }


def test_execute_state_proto_build_without_targets_keeps_empty_catalog():
    output = _build_output(
        (
            "玄力玄力玄力玄力玄力，神界神界神界。云澈在云荒镇休养。云澈成为少主。",
            "玄力玄力玄力，神界神界。茉莉还活着。",
        ),
        target_specs=(),
        novel_language="zh",
    )
    index = StateProtoIndex.from_msgpack(output.index_payload)

    assert output.target_count == 0
    assert output.mention_posting_count == 0
    assert output.claim_atom_count == 0
    assert index.targets == {}
    assert index.claim_atoms == []


def test_cue_detection_sets_historical_hypothetical_and_negated_flags():
    index = _build_index(
        (
            "闻昭曾在河湾书院查过旧案。",
            "若闻昭在北栈码头，就能先截住信使。",
            "闻昭不在云港司，而在河湾书院核对旧案。",
        ),
        target_specs=(TargetSpec(id="wen_zhao", canonical_name="闻昭"),),
    )

    cues_by_value = {
        (claim.value_signature, claim.cue_bitmap)
        for claim in index.claim_atoms
        if claim.key.slot == SLOT_ENTITY_CURRENT_LOCATION
    }

    assert ("河湾书院", CUE_HISTORICAL) in cues_by_value
    assert ("北栈码头", CUE_HYPOTHETICAL) in cues_by_value
    assert ("云港司", CUE_NEGATED) in cues_by_value


def test_location_extraction_requires_plausible_location_value_shape():
    index = _build_index(
        ("奥黛丽在女仆帮扶下站起，故意露出几分苦恼的神色。",),
        target_specs=(TargetSpec(id="audrey", canonical_name="奥黛丽"),),
    )

    location_claims = [
        claim
        for claim in index.claim_atoms
        if claim.key.target_id == "audrey"
        and claim.key.slot == SLOT_ENTITY_CURRENT_LOCATION
    ]
    assert location_claims == []


def test_clause_local_cue_detection_does_not_bleed_neighbor_negation():
    index = _build_index(
        ("两人都没有开口。克莱恩来到大祈祷厅，安静地站在门口。",),
        target_specs=(TargetSpec(id="klein", canonical_name="克莱恩"),),
    )

    location_claims = [
        claim
        for claim in index.claim_atoms
        if claim.key.target_id == "klein"
        and claim.key.slot == SLOT_ENTITY_CURRENT_LOCATION
    ]

    assert location_claims
    assert {claim.value_signature for claim in location_claims} == {"大祈祷厅"}
    assert all(claim.cue_bitmap == CUE_ASSERTED for claim in location_claims)


def test_entity_targets_do_not_emit_artifact_owner_claims():
    index = _build_index(
        ("奥黛丽手中拿着玄铁令，小心地收进袖袋。",),
        target_specs=(
            TargetSpec(id="audrey", canonical_name="奥黛丽"),
            TargetSpec(id="token", canonical_name="玄铁令"),
        ),
    )

    assert all(
        not (
            claim.key.target_id == "audrey"
            and claim.key.slot == "artifact.current_owner"
        )
        for claim in index.claim_atoms
    )


def test_life_state_extraction_requires_local_subject_binding():
    index = _build_index(
        ("伦纳德皱了皱眉，说海纳斯死了，但自己没有再补充。",),
        target_specs=(TargetSpec(id="leonard", canonical_name="伦纳德"),),
    )

    life_state_claims = [
        claim
        for claim in index.claim_atoms
        if claim.key.target_id == "leonard" and claim.key.slot == "entity.life_state"
    ]

    assert life_state_claims == []


def test_regime_merge_keeps_same_value_role_support_in_one_trace_row():
    case = next(
        case for case in build_state_proto_reference_cases() if case.case_id == "same_value_merge_role"
    )
    index = _build_index(case.chapters, target_specs=case.target_specs, novel_language=case.novel_language)

    trace = index.trace_slot(case.query_target_id, case.query_slot)

    assert len(trace.regimes) == 1
    assert trace.regimes[0].value_signature == case.expected_value
    assert trace.regimes[0].is_current_candidate is True


@pytest.mark.parametrize("case", build_state_proto_reference_cases(), ids=lambda case: case.case_id)
def test_fixture_cases_return_expected_top_value_and_uncertainty(case):
    index = _build_index(
        case.chapters,
        target_specs=case.target_specs,
        novel_language=case.novel_language,
    )

    packs = index.find_state(case.query_target_id, case.query_slot)
    assert packs, f"expected packs for {case.case_id}"

    top_pack = packs[0]
    trace = index.trace_slot(case.query_target_id, case.query_slot)

    assert top_pack.candidate_value_signature == case.expected_value
    assert top_pack.uncertainty_hint == case.expected_hint
    if case.expected_trace_regimes is not None:
        assert len(trace.regimes) == case.expected_trace_regimes


@pytest.mark.parametrize("case", build_state_proto_reference_cases(), ids=lambda case: case.case_id)
def test_pack_contract_budget_and_provenance(case):
    index = _build_index(
        case.chapters,
        target_specs=case.target_specs,
        novel_language=case.novel_language,
    )
    packs = index.find_state(case.query_target_id, case.query_slot)

    assert 1 <= len(packs) <= 2

    primary_pack = packs[0]
    preview_char_limit = (
        DEFAULT_CJK_PREVIEW_CHARS
        if case.novel_language == "zh"
        else DEFAULT_NON_CJK_PREVIEW_CHARS
    )
    open_char_limit = (
        DEFAULT_CJK_OPEN_CHARS
        if case.novel_language == "zh"
        else DEFAULT_NON_CJK_OPEN_CHARS
    )

    assert len(primary_pack.preview_excerpt) <= preview_char_limit

    primary_source = index.open(primary_pack.primary_handle)
    trace_payload = index.open(primary_pack.trace_handle)
    provenance = index.resolve_pack_provenance(primary_pack)

    assert len(primary_source.text) <= open_char_limit
    assert len(trace_payload.regimes) <= 4
    assert provenance.primary_claim.value_signature == primary_pack.candidate_value_signature
    assert provenance.segment.segment_id == provenance.primary_claim.segment_id
    assert provenance.source_payload.chapter_id == provenance.segment.chapter_id

    payload_budget = (
        index.estimate_payload_tokens(packs)
        + index.estimate_payload_tokens(primary_source)
        + index.estimate_payload_tokens(trace_payload)
    )
    if primary_pack.conflict_handle:
        payload_budget += index.estimate_payload_tokens(index.open(primary_pack.conflict_handle))

    assert payload_budget <= 3000


def test_execute_state_proto_build_incremental_matches_full_rebuild():
    target_specs = (TargetSpec(id="lin_qiu", canonical_name="林秋"),)
    original_chapters = [
        ChapterText(chapter_id=1, text="林秋在云港旧街盘货。"),
        ChapterText(chapter_id=2, text="夜里林秋来到北栈码头等船。"),
    ]
    base_output = execute_state_proto_build(
        chapters=original_chapters,
        novel_language="zh",
        target_specs=target_specs,
    )

    updated_chapters = [
        ChapterText(chapter_id=1, text="林秋在云港旧街盘货。"),
        ChapterText(chapter_id=2, text="夜里林秋来到河湾书院等人。"),
        ChapterText(chapter_id=3, text="后来林秋仍在河湾书院。"),
    ]
    incremental_output = execute_state_proto_build(
        chapters=updated_chapters,
        novel_language="zh",
        target_specs=target_specs,
        existing_payload=base_output.index_payload,
    )
    full_output = execute_state_proto_build(
        chapters=updated_chapters,
        novel_language="zh",
        target_specs=target_specs,
    )

    incremental_index = StateProtoIndex.from_msgpack(incremental_output.index_payload)
    full_index = StateProtoIndex.from_msgpack(full_output.index_payload)

    assert incremental_output.plan_mode == "incremental"
    assert incremental_output.incremental_applied is True
    assert incremental_output.rebuilt_chapter_count == 2
    assert incremental_index.find_state("lin_qiu", SLOT_ENTITY_CURRENT_LOCATION)[0].candidate_value_signature == "河湾书院"
    assert incremental_index.find_state("lin_qiu", SLOT_ENTITY_CURRENT_LOCATION)[0].candidate_value_signature == full_index.find_state("lin_qiu", SLOT_ENTITY_CURRENT_LOCATION)[0].candidate_value_signature
    assert {
        claim.claim_id
        for claim in incremental_index.claim_atoms
        if claim.chapter_number == 1
    } == {
        claim.claim_id
        for claim in full_index.claim_atoms
        if claim.chapter_number == 1
    }


def test_execute_state_proto_build_recovers_existing_payload_targets_when_catalog_is_omitted():
    original_chapters = [
        ChapterText(chapter_id=1, text="林秋在云港旧街盘货。"),
        ChapterText(chapter_id=2, text="夜里林秋来到北栈码头等船。"),
    ]
    base_output = execute_state_proto_build(
        chapters=original_chapters,
        novel_language="zh",
        target_specs=(TargetSpec(id="lin_qiu", canonical_name="林秋"),),
    )

    reuse_output = execute_state_proto_build(
        chapters=original_chapters,
        novel_language="zh",
        target_specs=None,
        existing_payload=base_output.index_payload,
    )
    assert reuse_output.plan_mode == "reuse_existing"
    assert reuse_output.rebuilt_chapter_count == 0
    assert reuse_output.reused_chapter_count == len(original_chapters)

    updated_chapters = [
        ChapterText(chapter_id=1, text="林秋在云港旧街盘货。"),
        ChapterText(chapter_id=2, text="夜里林秋来到河湾书院等人。"),
        ChapterText(chapter_id=3, text="后来林秋仍在河湾书院。"),
    ]
    incremental_output = execute_state_proto_build(
        chapters=updated_chapters,
        novel_language="zh",
        target_specs=None,
        existing_payload=base_output.index_payload,
    )
    full_output = execute_state_proto_build(
        chapters=updated_chapters,
        novel_language="zh",
        target_specs=(TargetSpec(id="lin_qiu", canonical_name="林秋"),),
    )

    incremental_index = StateProtoIndex.from_msgpack(incremental_output.index_payload)
    full_index = StateProtoIndex.from_msgpack(full_output.index_payload)

    assert incremental_output.plan_mode == "incremental"
    assert incremental_output.incremental_applied is True
    assert incremental_output.rebuilt_chapter_count == 2
    assert incremental_output.reused_chapter_count == 1
    assert (
        incremental_index.find_state("lin_qiu", SLOT_ENTITY_CURRENT_LOCATION)[0].candidate_value_signature
        == "河湾书院"
    )
    assert (
        incremental_index.find_state("lin_qiu", SLOT_ENTITY_CURRENT_LOCATION)[0].candidate_value_signature
        == full_index.find_state("lin_qiu", SLOT_ENTITY_CURRENT_LOCATION)[0].candidate_value_signature
    )


def test_state_proto_payload_loads_through_window_index_compat():
    output = execute_state_proto_build(
        chapters=[
            ChapterText(chapter_id=1, text="林秋在云港旧街盘货。"),
            ChapterText(chapter_id=2, text="夜里林秋来到北栈码头等船。"),
        ],
        novel_language="zh",
        target_specs=(TargetSpec(id="lin_qiu", canonical_name="林秋"),),
    )

    compat_index = NovelIndex.from_msgpack(output.index_payload)
    passages = compat_index.find_entity_passages("林秋", limit=4)

    assert passages
    assert passages[0].chapter_id in {1, 2}
