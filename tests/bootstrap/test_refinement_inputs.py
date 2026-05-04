from __future__ import annotations

from collections import Counter
from itertools import combinations

import app.core.bootstrap_text_fallback as text_fallback_module
from app.config import get_settings
from app.core.bootstrap_refinement import (
    BootstrapRefinementResult,
    RefinedEntity,
    _build_refinement_prompt,
    _select_refinement_prompt_shortlist,
    build_bootstrap_refinement_inputs,
    sanitize_bootstrap_refinement_result,
)
from app.core.bootstrap_text_fallback import (
    build_cjk_refinement_inputs_from_shortlist,
    build_refinement_inputs_from_text_candidates,
    count_window_offsets,
    extract_text_candidate_counts,
    resolve_text_fallback_window_threshold,
    window_offsets,
)
from app.core.indexing.builder import ChapterText, load_common_words
from app.core.indexing.state_proto_model import CoverageRepresentative, MentionPosting
from app.core.indexing.state_proto_model import TargetSpec
from app.core.indexing.state_proto_runtime import Segment, StateProtoIndex
from app.core.indexing.state_proto_rust_contract import rust_state_proto_is_available
from app.core.indexing.state_proto_rust_text import RustZhBlockRefinementSummary


def test_build_bootstrap_refinement_inputs_uses_state_proto_payload_summary():
    inputs = build_bootstrap_refinement_inputs(
        index_payload=StateProtoIndex(
            language="en",
            targets={
                "alice": TargetSpec(id="alice", canonical_name="Alice"),
                "bob": TargetSpec(id="bob", canonical_name="Bob"),
            },
            segments=[
                Segment(
                    segment_id=1,
                    chapter_id=1,
                    chapter_number=1,
                    start_pos=0,
                    end_pos=40,
                    progress_bucket=0,
                )
            ],
            mention_postings=[
                MentionPosting(
                    target_id="alice",
                    segment_id=1,
                    mention_score=1.0,
                    density=1.0,
                    best_anchor_offset=0,
                ),
                MentionPosting(
                    target_id="bob",
                    segment_id=1,
                    mention_score=1.0,
                    density=1.0,
                    best_anchor_offset=10,
                ),
            ],
            coverage_reps=[
                CoverageRepresentative(
                    target_id="alice",
                    bucket_id=0,
                    segment_id=1,
                    rep_score=1.0,
                ),
                CoverageRepresentative(
                    target_id="bob",
                    bucket_id=0,
                    segment_id=1,
                    rep_score=1.0,
                ),
            ],
        ).to_msgpack(),
        chapters=[],
        novel_language="en",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=20,
        include_text_fallback=False,
    )

    assert inputs.importance["Alice"] > 0
    assert any(
        {left, right} == {"Alice", "Bob"}
        for left, right, _ in inputs.cooccurrence_pairs
    )
    assert inputs.supplemental_candidate_count == 0
    assert inputs.supplemental_pair_count == 0


def test_build_bootstrap_refinement_inputs_can_fall_back_to_text_candidates():
    inputs = build_bootstrap_refinement_inputs(
        index_payload=None,
        chapters=[
            ChapterText(
                chapter_id=1,
                text=(
                    "Alice met Bob in Paris. Charlie joined Alice and Bob later. " * 80
                ).strip(),
            ),
        ],
        novel_language="en",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=20,
        include_text_fallback=True,
    )

    assert inputs.importance["Alice"] > 0
    assert inputs.importance["Bob"] > 0
    assert inputs.supplemental_candidate_count == len(inputs.importance)
    assert inputs.supplemental_pair_count == len(inputs.cooccurrence_pairs)
    assert any(
        {left, right} == {"Alice", "Bob"}
        for left, right, _ in inputs.cooccurrence_pairs
    )


def test_build_bootstrap_refinement_inputs_preserves_state_proto_alias_candidates():
    inputs = build_bootstrap_refinement_inputs(
        index_payload=StateProtoIndex(
            language="en",
            targets={
                "john": TargetSpec(
                    id="john",
                    canonical_name="John Smith",
                    aliases=("Mr. Smith", "John"),
                ),
                "alice": TargetSpec(id="alice", canonical_name="Alice"),
            },
            segments=[
                Segment(
                    segment_id=1,
                    chapter_id=1,
                    chapter_number=1,
                    start_pos=0,
                    end_pos=40,
                    progress_bucket=0,
                )
            ],
            mention_postings=[
                MentionPosting(
                    target_id="john",
                    segment_id=1,
                    mention_score=1.0,
                    density=1.0,
                    best_anchor_offset=0,
                ),
                MentionPosting(
                    target_id="alice",
                    segment_id=1,
                    mention_score=1.0,
                    density=1.0,
                    best_anchor_offset=10,
                ),
            ],
            coverage_reps=[
                CoverageRepresentative(
                    target_id="john",
                    bucket_id=0,
                    segment_id=1,
                    rep_score=1.0,
                )
            ],
        ).to_msgpack(),
        chapters=[],
        novel_language="en",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=20,
        include_text_fallback=False,
    )

    assert "John Smith" in inputs.allowed_alias_candidates
    assert "Mr. Smith" in inputs.allowed_alias_candidates
    assert "John" in inputs.allowed_alias_candidates


def test_build_refinement_inputs_from_text_candidates_supports_cjk_windows():
    importance, pairs = build_refinement_inputs_from_text_candidates(
        [
            ChapterText(
                chapter_id=1,
                text=("林秋在云港司守夜，顾衡来找林秋。顾衡与林秋又在云港司说起旧案。")
                * 40,
            ),
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=20,
    )

    assert importance["林秋"] > 0
    assert importance["顾衡"] > 0
    assert any({left, right} == {"林秋", "顾衡"} for left, right, _ in pairs)


def test_extract_text_candidate_counts_is_stable_across_chapter_boundaries():
    split_language, split_counts = extract_text_candidate_counts(
        [
            ChapterText(chapter_id=1, text="林秋在云港司守夜。"),
            ChapterText(chapter_id=2, text="顾衡来找林秋。"),
            ChapterText(chapter_id=3, text="云港司里再次提起顾衡。"),
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )
    combined_language, combined_counts = extract_text_candidate_counts(
        [
            ChapterText(
                chapter_id=1,
                text="林秋在云港司守夜。\n\n顾衡来找林秋。\n\n云港司里再次提起顾衡。",
            )
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert split_language == combined_language == "zh"
    assert split_counts == combined_counts
    assert split_counts["林秋"] == 2
    assert split_counts["顾衡"] == 2


def test_extract_text_candidate_counts_recovers_split_zh_person_names():
    language, counts = extract_text_candidate_counts(
        [
            ChapterText(
                chapter_id=1,
                text=(
                    "慕容雪晴来到大厅。慕容雪晴看着欧阳明月，欧阳明月也看着慕容雪晴。"
                    "顾慎为与荷女对视。顾慎为没有说话。"
                ),
            )
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert language == "zh"
    assert counts["慕容雪晴"] == 3
    assert counts["欧阳明月"] == 2
    assert counts["顾慎为"] == 2


def test_extract_text_candidate_counts_trusts_rust_split_name_recovery(monkeypatch):
    if not rust_state_proto_is_available():
        return

    def _should_not_run(*args, **kwargs):
        raise AssertionError("python split-name recovery should not run on rust fast path")

    monkeypatch.setattr(
        text_fallback_module,
        "_count_likely_zh_split_names",
        _should_not_run,
    )

    language, counts = extract_text_candidate_counts(
        [
            ChapterText(
                chapter_id=1,
                text=(
                    "慕容雪晴来到大厅。慕容雪晴看着欧阳明月，欧阳明月也看着慕容雪晴。"
                    "顾慎为与荷女对视。顾慎为没有说话。"
                ),
            )
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert language == "zh"
    assert counts["慕容雪晴"] == 3


def test_build_refinement_inputs_from_text_candidates_keeps_recovered_full_names():
    importance, pairs = build_refinement_inputs_from_text_candidates(
        [
            ChapterText(
                chapter_id=1,
                text=(
                    "慕容雪晴来到大厅。慕容雪晴看着欧阳明月，欧阳明月也看着慕容雪晴。"
                    "顾慎为与荷女对视。顾慎为没有说话，荷女只是冷笑。"
                )
                * 24,
            ),
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=24,
    )

    assert importance["慕容雪晴"] > 0
    assert importance["欧阳明月"] > 0
    assert importance["顾慎为"] > 0
    assert any({left, right} == {"慕容雪晴", "欧阳明月"} for left, right, _ in pairs)


def test_extract_text_candidate_counts_recovers_bound_zh_fragment_names():
    language, counts = extract_text_candidate_counts(
        [
            ChapterText(
                chapter_id=1,
                text=(
                    "拉蒂莉娅看见坎贝斯莉太太。"
                    "拉蒂莉娅向坎贝斯莉太太行礼。"
                    "拉蒂莉娅又遇见坎贝斯莉太太。"
                ),
            )
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert language == "zh"
    assert counts["拉蒂莉娅"] == 3
    assert counts["坎贝斯莉太太"] == 3
    assert counts.get("拉蒂", 0) == 0
    assert counts.get("贝斯", 0) == 0
    assert counts.get("太太", 0) == 0


def test_build_refinement_inputs_from_text_candidates_trusts_rust_split_name_recovery(
    monkeypatch,
):
    if not rust_state_proto_is_available():
        return

    def _should_not_run(*args, **kwargs):
        raise AssertionError("python split-name recovery should not run on rust fast path")

    monkeypatch.setattr(
        text_fallback_module,
        "_count_likely_zh_split_names",
        _should_not_run,
    )

    importance, pairs = build_refinement_inputs_from_text_candidates(
        [
            ChapterText(
                chapter_id=1,
                text=(
                    "慕容雪晴来到大厅。慕容雪晴看着欧阳明月，欧阳明月也看着慕容雪晴。"
                    "顾慎为与荷女对视。顾慎为没有说话，荷女只是冷笑。"
                )
                * 24,
            ),
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=24,
    )

    assert importance["慕容雪晴"] > 0
    assert any({left, right} == {"慕容雪晴", "欧阳明月"} for left, right, _ in pairs)


def test_build_refinement_inputs_from_text_candidates_prefers_rust_block_builder(
    monkeypatch,
):
    def _fake_block_builder(**kwargs):
        assert kwargs["limit"] == 24
        return RustZhBlockRefinementSummary(
            importance={"林秋": 9, "顾衡": 7},
            cooccurrence_pairs=[("林秋", "顾衡", 5)],
            canonical_surfaces={"林秋": ("林秋",), "顾衡": ("顾衡",)},
        )

    monkeypatch.setattr(
        text_fallback_module,
        "build_rust_zh_block_refinement_inputs",
        _fake_block_builder,
    )
    monkeypatch.setattr(
        text_fallback_module,
        "count_rust_zh_candidates",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy rust candidate path should be bypassed")
        ),
    )
    monkeypatch.setattr(
        text_fallback_module,
        "summarize_rust_zh_windows",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy rust window path should be bypassed")
        ),
    )

    importance, pairs = build_refinement_inputs_from_text_candidates(
        [ChapterText(chapter_id=1, text="林秋与顾衡守夜。")],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=24,
    )

    assert importance == {"林秋": 9, "顾衡": 7}
    assert pairs == [("林秋", "顾衡", 5)]


def test_build_bootstrap_refinement_inputs_keeps_rust_canonical_surface_alias_candidates(
    monkeypatch,
):
    def _fake_block_builder(**kwargs):
        assert kwargs["limit"] == 24
        return RustZhBlockRefinementSummary(
            importance={"凤雪儿": 9, "云澈": 7},
            cooccurrence_pairs=[("凤雪儿", "云澈", 5)],
            canonical_surfaces={"凤雪儿": ("凤雪儿", "凤雪児"), "云澈": ("云澈",)},
        )

    monkeypatch.setattr(
        text_fallback_module,
        "build_rust_zh_block_refinement_inputs",
        _fake_block_builder,
    )

    inputs = build_bootstrap_refinement_inputs(
        index_payload=None,
        chapters=[ChapterText(chapter_id=1, text="凤雪児看向云澈。")],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=24,
        include_text_fallback=True,
    )

    assert "凤雪児" in inputs.allowed_alias_candidates
    assert "凤雪児" in inputs.supported_alias_candidates


def test_build_refinement_inputs_from_text_candidates_uses_bound_fragment_full_names():
    importance, pairs = build_refinement_inputs_from_text_candidates(
        [
            ChapterText(
                chapter_id=1,
                text=(
                    "柯启看见拉蒂莉娅。柯启又遇见拉蒂莉娅。"
                    "坎贝斯莉太太带着拉蒂莉娅离开。"
                )
                * 16,
            ),
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
        limit=24,
    )

    assert importance["拉蒂莉娅"] > 0
    assert importance["坎贝斯莉太太"] > 0
    assert any({left, right} == {"柯启", "拉蒂莉娅"} for left, right, _ in pairs)


def test_sanitize_bootstrap_refinement_result_drops_alias_noise():
    cleaned = sanitize_bootstrap_refinement_result(
        BootstrapRefinementResult(
            entities=[
                RefinedEntity(name="张纲", aliases=["张纲一", "前来", "纲哥"]),
                RefinedEntity(name="顾慎为", aliases=["顾兄", "顾慎为"]),
            ],
            relationships=[],
        ),
        allowed_candidates=["张纲", "张纲一", "前来", "纲哥", "顾兄", "顾慎为"],
        novel_language="zh",
    )

    aliases_by_name = {entity.name: entity.aliases for entity in cleaned.entities}
    assert aliases_by_name["张纲"] == ["纲哥"]
    assert aliases_by_name["顾慎为"] == ["顾兄"]


def test_sanitize_bootstrap_refinement_result_keeps_supported_zh_title_aliases():
    cleaned = sanitize_bootstrap_refinement_result(
        BootstrapRefinementResult(
            entities=[
                RefinedEntity(name="顾慎为", aliases=["龙王", "前来"]),
            ],
            relationships=[],
        ),
        allowed_candidates=["顾慎为", "龙王", "前来"],
        supported_alias_candidates=["龙王"],
        novel_language="zh",
    )

    assert cleaned.entities[0].aliases == ["龙王"]


def test_sanitize_bootstrap_refinement_result_keeps_zh_surface_variants():
    cleaned = sanitize_bootstrap_refinement_result(
        BootstrapRefinementResult(
            entities=[
                RefinedEntity(name="凤雪儿", aliases=["凤雪児"]),
            ],
            relationships=[],
        ),
        allowed_candidates=["凤雪儿", "凤雪児"],
        novel_language="zh",
    )

    assert cleaned.entities[0].aliases == ["凤雪児"]


def test_prompt_shortlist_demotes_zh_narrative_phrases():
    candidates, _ = _select_refinement_prompt_shortlist(
        {
            "柯启": 30,
            "莉娅": 28,
            "游戏": 23,
            "一时间": 11,
            "李周": 8,
            "都没有": 10,
        },
        [
            ("柯启", "一时间", 11),
            ("柯启", "莉娅", 10),
            ("柯启", "游戏", 10),
            ("李周", "柯启", 7),
            ("柯启", "都没有", 10),
        ],
        max_candidates=4,
        max_pairs=4,
        novel_language="zh",
    )

    candidate_names = [name for name, _ in candidates]
    assert "柯启" in candidate_names
    assert "莉娅" in candidate_names
    assert "游戏" in candidate_names
    assert "李周" in candidate_names
    assert "一时间" not in candidate_names
    assert "都没有" not in candidate_names


def test_prompt_shortlist_pair_ranking_prefers_entity_pairs_over_narrative_phrase_pairs():
    _, pairs = _select_refinement_prompt_shortlist(
        {
            "柯启": 30,
            "莉娅": 28,
            "游戏": 23,
            "一时间": 11,
            "李周": 8,
            "都没有": 10,
        },
        [
            ("柯启", "一时间", 11),
            ("柯启", "莉娅", 10),
            ("柯启", "游戏", 10),
            ("李周", "柯启", 7),
            ("柯启", "都没有", 10),
        ],
        max_candidates=5,
        max_pairs=2,
        novel_language="zh",
    )

    assert pairs == [("柯启", "莉娅", 10), ("柯启", "游戏", 10)]


def test_prompt_shortlist_suppresses_dominant_zh_prefix_shadow_names():
    candidates, _ = _select_refinement_prompt_shortlist(
        {
            "顾慎": 100,
            "顾慎为": 99,
            "龙王": 80,
            "荷女": 70,
            "方闻": 60,
            "方闻是": 60,
        },
        [
            ("顾慎为", "龙王", 8),
            ("龙王", "荷女", 7),
            ("方闻是", "龙王", 6),
        ],
        max_candidates=4,
        max_pairs=4,
        novel_language="zh",
    )

    candidate_names = [name for name, _ in candidates]
    assert "顾慎为" in candidate_names
    assert "顾慎" not in candidate_names
    assert "方闻是" in candidate_names
    assert "方闻" not in candidate_names


def test_prompt_shortlist_keeps_ambiguous_zh_family_prefixes():
    candidates, _ = _select_refinement_prompt_shortlist(
        {
            "上官": 100,
            "上官如": 55,
            "上官飞": 54,
            "荷女": 70,
            "龙王": 68,
        },
        [
            ("上官", "龙王", 8),
            ("上官如", "荷女", 7),
            ("上官飞", "荷女", 7),
        ],
        max_candidates=4,
        max_pairs=4,
        novel_language="zh",
    )

    candidate_names = [name for name, _ in candidates]
    assert "上官" in candidate_names


def test_prompt_shortlist_prefers_entity_like_surfaces_over_generic_backdrop_words():
    candidates, _ = _select_refinement_prompt_shortlist(
        {
            "世界": 350,
            "文明": 300,
            "材料": 260,
            "嘉德丽雅": 120,
            "塔罗会": 118,
            "红岸基地": 110,
            "杨冬": 105,
        },
        [
            ("嘉德丽雅", "塔罗会", 7),
            ("杨冬", "红岸基地", 6),
            ("世界", "文明", 25),
            ("世界", "材料", 20),
        ],
        max_candidates=6,
        max_pairs=4,
        novel_language="zh",
    )

    candidate_names = [name for name, _ in candidates]
    assert "嘉德丽雅" in candidate_names
    assert "杨冬" in candidate_names
    assert "塔罗会" in candidate_names
    assert "红岸基地" in candidate_names
    assert "材料" not in candidate_names
    assert candidate_names.index("嘉德丽雅") < candidate_names.index("世界")


def test_extract_text_candidate_counts_rust_fast_path_matches_python_fallback(
    monkeypatch,
):
    chapters = [
        ChapterText(chapter_id=1, text="林秋在云港司守夜。"),
        ChapterText(chapter_id=2, text="顾衡来找林秋。"),
        ChapterText(chapter_id=3, text="云港司里再次提起顾衡。"),
    ]

    rust_language, rust_counts = extract_text_candidate_counts(
        chapters,
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )
    monkeypatch.setattr(
        text_fallback_module,
        "count_rust_zh_candidates",
        lambda **kwargs: None,
    )
    python_language, python_counts = extract_text_candidate_counts(
        chapters,
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert rust_language == python_language == "zh"
    assert rust_counts == python_counts


def test_extract_text_candidate_counts_rust_fast_path_matches_python_fallback_for_bound_fragments(
    monkeypatch,
):
    chapters = [
        ChapterText(
            chapter_id=1,
            text=(
                "拉蒂莉娅看见坎贝斯莉太太。"
                "拉蒂莉娅向坎贝斯莉太太行礼。"
                "拉蒂莉娅又遇见坎贝斯莉太太。"
            ),
        )
    ]

    rust_language, rust_counts = extract_text_candidate_counts(
        chapters,
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )
    monkeypatch.setattr(
        text_fallback_module,
        "count_rust_zh_candidates",
        lambda **kwargs: None,
    )
    python_language, python_counts = extract_text_candidate_counts(
        chapters,
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert rust_language == python_language == "zh"
    assert rust_counts == python_counts


def test_build_cjk_refinement_inputs_from_shortlist_matches_reference_window_counts():
    chapters = [
        ChapterText(
            chapter_id=1,
            text=("林秋在云港司守夜，顾衡来找林秋。顾衡与林秋又在云港司说起旧案。")
            * 20,
        ),
        ChapterText(
            chapter_id=2,
            text=("云港司里再次提起旧案，林秋仍在查。顾衡这次没有离开云港司。") * 18,
        ),
    ]
    shortlisted_candidates = ["林秋", "顾衡", "云港司", "旧案"]

    names_by_id, importance, pair_counts, total_windows = (
        build_cjk_refinement_inputs_from_shortlist(
            chapters,
            shortlisted_candidates=shortlisted_candidates,
        )
        or ((), {}, {}, 0)
    )

    reference_importance_counter: Counter[str] = Counter()
    reference_pair_counts: Counter[tuple[str, str]] = Counter()
    reference_total_windows = 0
    for chapter in chapters:
        chapter_text = chapter.text or ""
        if not chapter_text.strip():
            continue
        for start_pos in window_offsets(len(chapter_text), 500, 250):
            reference_total_windows += 1
            window_text = chapter_text[start_pos : start_pos + 500]
            present_names = {
                candidate
                for candidate in shortlisted_candidates
                if candidate in window_text
            }
            if not present_names:
                continue
            for name in present_names:
                reference_importance_counter[name] += 1
            for left, right in combinations(sorted(present_names), 2):
                reference_pair_counts[(left, right)] += 1

    threshold = resolve_text_fallback_window_threshold(reference_total_windows)
    reference_importance = {
        name: count
        for name, count in reference_importance_counter.items()
        if count >= threshold
    }
    decoded_pair_counts = {
        (names_by_id[left_id], names_by_id[right_id]): count
        for pair_key, count in pair_counts.items()
        for left_id, right_id in [divmod(pair_key, len(names_by_id))]
    }
    reference_filtered_pairs = {
        pair: count
        for pair, count in reference_pair_counts.items()
        if pair[0] in reference_importance and pair[1] in reference_importance
    }

    assert total_windows == reference_total_windows
    assert importance == reference_importance
    assert decoded_pair_counts == reference_filtered_pairs


def test_extract_text_candidate_counts_hard_drops_curated_zh_shortlist_noise(monkeypatch):
    monkeypatch.setattr(
        text_fallback_module,
        "extract_rust_zh_sorted_candidates",
        lambda *args, **kwargs: None,
    )

    def _fake_tokenize_text(text: str, *, language: str):
        del text
        assert language == "zh"
        return "zh", [
            "林秋",
            "一看",
            "顾衡",
            "赶紧",
            "打开",
            "手里",
            "取出",
            "令牌",
            "拿出",
            "可不",
            "特么",
            "听说",
            "打算",
            "跟着",
            "这会儿",
            "肯定",
            "家里",
            "晚上",
            "要不",
            "话说",
            "谁知",
            "着呢",
            "不得了",
            "那会儿",
            "二话不说",
            "不经意",
            "急匆匆",
            "暗地里",
            "林秋",
        ]

    monkeypatch.setattr(text_fallback_module, "tokenize_text", _fake_tokenize_text)

    common_words = load_common_words(
        "zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )
    for noise in (
        "可不",
        "特么",
        "一看",
        "赶紧",
        "取出",
        "拿出",
        "打算",
        "跟着",
        "听说",
        "肯定",
        "这会儿",
        "手里",
        "家里",
        "晚上",
        "打开",
        "要不",
        "话说",
        "谁知",
        "着呢",
        "不得了",
        "那会儿",
        "二话不说",
        "不经意",
        "急匆匆",
        "暗地里",
    ):
        assert noise in common_words

    language, counts = extract_text_candidate_counts(
        [ChapterText(chapter_id=1, text="ignored")],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert language == "zh"
    assert counts["林秋"] == 2
    assert counts["顾衡"] == 1
    assert counts["令牌"] == 1
    for noise in (
        "可不",
        "特么",
        "一看",
        "赶紧",
        "取出",
        "拿出",
        "打算",
        "跟着",
        "听说",
        "肯定",
        "这会儿",
        "手里",
        "家里",
        "晚上",
        "打开",
        "要不",
        "话说",
        "谁知",
        "着呢",
        "不得了",
        "那会儿",
        "二话不说",
        "不经意",
        "急匆匆",
        "暗地里",
    ):
        assert noise not in counts


def test_extract_text_candidate_counts_merges_zh_person_name_trailing_noise(monkeypatch):
    monkeypatch.setattr(
        text_fallback_module,
        "extract_rust_zh_sorted_candidates",
        lambda *args, **kwargs: None,
    )

    def _fake_tokenize_text(text: str, *, language: str):
        del text
        assert language == "zh"
        return "zh", [
            "罗碧",
            "罗碧不",
            "罗碧一",
            "罗碧看",
            "罗碧没",
            "罗碧也",
            "罗碧就",
            "凤凌",
            "炙皇星看",
        ]

    monkeypatch.setattr(text_fallback_module, "tokenize_text", _fake_tokenize_text)

    language, counts = extract_text_candidate_counts(
        [ChapterText(chapter_id=1, text="ignored")],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert language == "zh"
    assert counts["罗碧"] == 7
    assert counts["凤凌"] == 1
    assert counts["炙皇星看"] == 1
    assert "罗碧不" not in counts
    assert "罗碧一" not in counts
    assert "罗碧看" not in counts
    assert "罗碧没" not in counts
    assert "罗碧也" not in counts
    assert "罗碧就" not in counts


def test_extract_text_candidate_counts_rust_fast_path_matches_python_fallback_for_trailing_noise_names(
    monkeypatch,
):
    chapters = [
        ChapterText(
            chapter_id=1,
            text="罗碧不，凤凌。罗碧一，凤凌。罗碧看，凤凌。罗碧没，凤凌。罗碧，凤凌。",
        )
    ]

    rust_language, rust_counts = extract_text_candidate_counts(
        chapters,
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )
    monkeypatch.setattr(
        text_fallback_module,
        "extract_rust_zh_sorted_candidates",
        lambda *args, **kwargs: None,
    )
    python_language, python_counts = extract_text_candidate_counts(
        chapters,
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert rust_language == python_language == "zh"
    assert rust_counts == python_counts
    assert rust_counts["罗碧"] >= 5
    assert "罗碧不" not in rust_counts
    assert "罗碧一" not in rust_counts
    assert "罗碧看" not in rust_counts
    assert "罗碧没" not in rust_counts


def test_extract_text_candidate_counts_normalizes_zh_variant_characters():
    language, counts = extract_text_candidate_counts(
        [
            ChapterText(
                chapter_id=1,
                text="凤雪児看向云澈。凤雪児再次叫住云澈。凤雪児握住云澈的手。",
            )
        ],
        novel_language="zh",
        common_words_dir=get_settings().bootstrap_common_words_dir,
    )

    assert language == "zh"
    assert counts["凤雪儿"] >= 3
    assert "凤雪児" not in counts


def test_text_fallback_threshold_caps_for_long_manuscripts():
    assert resolve_text_fallback_window_threshold(1) == 1
    assert resolve_text_fallback_window_threshold(300) == 3
    assert resolve_text_fallback_window_threshold(4000) == 8


def test_count_window_offsets_matches_explicit_offsets():
    for text_length in (0, 1, 499, 500, 501, 750, 751, 1000, 1001, 4000):
        assert count_window_offsets(text_length, 500, 250) == len(
            window_offsets(text_length, 500, 250)
        )


def test_build_refinement_prompt_prefers_specific_places_and_organizations():
    prompt = _build_refinement_prompt(
        {"炙皇星": 12, "皇星": 20, "星际": 50, "契师学院": 9},
        [("罗碧", "炙皇星", 5)],
        max_candidates=10,
        max_pairs=20,
        max_entities=10,
        max_relationships=20,
        prompt_locale="zh",
    )

    assert "优先保留更具体的专有名词" in prompt
    assert "契师学院" in prompt
    assert "星际" in prompt
