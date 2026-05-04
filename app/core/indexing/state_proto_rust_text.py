from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .builder import ChapterText
from .state_proto_rust_module import get_rust_state_proto_module


@dataclass(frozen=True, slots=True)
class RustZhWindowSummary:
    importance: dict[str, int]
    cooccurrence_pairs: list[tuple[str, str, int]]


@dataclass(frozen=True, slots=True)
class RustZhCandidateCount:
    name: str
    count: int


@dataclass(frozen=True, slots=True)
class RustZhBlockRefinementSummary:
    importance: dict[str, int]
    cooccurrence_pairs: list[tuple[str, str, int]]
    canonical_surfaces: dict[str, tuple[str, ...]]


def summarize_rust_zh_windows(
    *,
    chapters: Sequence[ChapterText],
    shortlisted_candidates: Sequence[str],
    window_size: int,
    window_step: int,
    threshold: int,
) -> RustZhWindowSummary | None:
    rust_module = get_rust_state_proto_module()
    if rust_module is None:
        return None
    rust_summary_compact = getattr(rust_module, "summarize_zh_windows_compact", None)
    rust_summary = getattr(rust_module, "summarize_zh_windows", None)
    if rust_summary is None and rust_summary_compact is None:
        return None

    chapter_texts = [chapter.text or "" for chapter in chapters if chapter.text]
    if not chapter_texts:
        return RustZhWindowSummary(importance={}, cooccurrence_pairs=[])

    shortlist = list(shortlisted_candidates)
    if rust_summary_compact is not None:
        candidate_names, raw_importance, raw_pairs = rust_summary_compact(
            chapter_texts,
            shortlist,
            int(window_size),
            int(window_step),
            int(threshold),
        )
        if not candidate_names:
            return RustZhWindowSummary(importance={}, cooccurrence_pairs=[])
        candidate_names = tuple(str(name) for name in candidate_names)
        return RustZhWindowSummary(
            importance={
                candidate_names[int(candidate_id)]: int(count)
                for candidate_id, count in raw_importance
            },
            cooccurrence_pairs=[
                (
                    candidate_names[int(left_id)],
                    candidate_names[int(right_id)],
                    int(count),
                )
                for left_id, right_id, count in raw_pairs
            ],
        )

    raw_importance, raw_pairs = rust_summary(
        chapter_texts,
        shortlist,
        int(window_size),
        int(window_step),
        int(threshold),
    )
    return RustZhWindowSummary(
        importance={str(name): int(count) for name, count in raw_importance},
        cooccurrence_pairs=[
            (str(left), str(right), int(count)) for left, right, count in raw_pairs
        ],
    )


def count_rust_zh_candidates(
    *,
    chapters: Sequence[ChapterText],
    common_words: Sequence[str],
    max_batch_chars: int,
    limit: int | None = None,
) -> list[RustZhCandidateCount] | None:
    rust_module = get_rust_state_proto_module()
    if rust_module is None:
        return None
    rust_topk_counter = getattr(rust_module, "count_zh_candidates_topk", None)
    rust_counter = getattr(rust_module, "count_zh_candidates", None)
    if rust_counter is None and rust_topk_counter is None:
        return None

    chapter_texts = [chapter.text or "" for chapter in chapters if chapter.text]
    if not chapter_texts:
        return []

    common_words_list = list(common_words)
    if rust_topk_counter is not None and limit is not None:
        raw_counts = rust_topk_counter(
            chapter_texts,
            common_words_list,
            int(max_batch_chars),
            max(int(limit), 0),
        )
    else:
        if rust_counter is None:
            return None
        raw_counts = rust_counter(
            chapter_texts,
            common_words_list,
            int(max_batch_chars),
        )

    return [
        RustZhCandidateCount(name=str(name), count=int(count))
        for name, count in raw_counts
    ]


def build_rust_zh_block_refinement_inputs(
    *,
    chapters: Sequence[ChapterText],
    common_words: Sequence[str],
    limit: int,
) -> RustZhBlockRefinementSummary | None:
    rust_module = get_rust_state_proto_module()
    if rust_module is None:
        return None
    rust_builder = getattr(rust_module, "build_zh_block_refinement_inputs_compact", None)
    if rust_builder is None:
        return None

    chapter_texts = [chapter.text or "" for chapter in chapters if chapter.text]
    if not chapter_texts:
        return RustZhBlockRefinementSummary(
            importance={},
            cooccurrence_pairs=[],
            canonical_surfaces={},
        )

    surface_names, raw_importance, raw_pairs, raw_canonical_surfaces = rust_builder(
        chapter_texts,
        list(common_words),
        max(int(limit), 0),
    )
    if not surface_names:
        return RustZhBlockRefinementSummary(
            importance={},
            cooccurrence_pairs=[],
            canonical_surfaces={},
        )

    surface_names = tuple(str(name) for name in surface_names)
    return RustZhBlockRefinementSummary(
        importance={
            surface_names[int(surface_id)]: int(count)
            for surface_id, count in raw_importance
        },
        cooccurrence_pairs=[
            (
                surface_names[int(left_id)],
                surface_names[int(right_id)],
                int(count),
            )
            for left_id, right_id, count in raw_pairs
        ],
        canonical_surfaces={
            surface_names[int(canonical_id)]: tuple(
                surface_names[int(surface_id)] for surface_id in surface_ids
            )
            for canonical_id, surface_ids in raw_canonical_surfaces
        },
    )
