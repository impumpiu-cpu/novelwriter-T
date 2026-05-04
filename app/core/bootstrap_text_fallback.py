from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
import math
import re
from typing import Callable, Sequence

try:
    import ahocorasick
except ImportError:  # pragma: no cover - dependency is required in production
    ahocorasick = None

from app.core.indexing.builder import ChapterText, load_common_words, tokenize_text
from app.core.indexing.state_proto_rust_text import (
    RustZhBlockRefinementSummary,
    RustZhCandidateCount,
    RustZhWindowSummary,
    build_rust_zh_block_refinement_inputs,
    count_rust_zh_candidates,
    summarize_rust_zh_windows,
)
from app.core.indexing.zh_name_rules import (
    get_zh_name_suffix_titles,
    get_zh_translit_chars,
    is_cjk_name_token,
    is_zh_name_suffix_title,
    looks_like_zh_translit_fragment,
    looks_like_zh_person_name,
    strip_zh_person_name_trailing_noise,
)
from app.language_policy import get_language_policy, resolve_text_processing_language

TEXT_FALLBACK_WINDOW_SIZE = 500
TEXT_FALLBACK_WINDOW_STEP = 250
TEXT_FALLBACK_TOKENIZE_BATCH_CHARS = 256 * 1024
TEXT_FALLBACK_MIN_WINDOW_COUNT = 3
TEXT_FALLBACK_MIN_WINDOW_RATIO = 0.005
TEXT_FALLBACK_MAX_WINDOW_THRESHOLD = 8
TEXT_FALLBACK_CANDIDATE_MULTIPLIER = 4
TEXT_FALLBACK_CANDIDATE_HARD_CAP = 512
TEXT_FALLBACK_ZH_SPLIT_NAME_MIN_COUNT = 2
TEXT_FALLBACK_ZH_FRAGMENT_EXTENSION_MIN_COUNT = 3
TEXT_FALLBACK_ZH_FRAGMENT_DOMINANCE_THRESHOLD = 0.85
TEXT_FALLBACK_ZH_FRAGMENT_MAX_TOKEN_CHARS = 3

RustZhCandidateCounter = Callable[..., list[RustZhCandidateCount] | None]
RustZhBlockRefinementBuilder = Callable[..., RustZhBlockRefinementSummary | None]
RustZhWindowSummarizer = Callable[..., RustZhWindowSummary | None]
_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


@dataclass(frozen=True, slots=True)
class TextRefinementInputs:
    importance: dict[str, int]
    cooccurrence_pairs: list[tuple[str, str, int]]
    allowed_alias_candidates: frozenset[str] = frozenset()
    supported_alias_candidates: frozenset[str] = frozenset()


def _count_likely_zh_split_names(
    chapters: Sequence[ChapterText],
    *,
    language: str,
    common_words: set[str],
) -> Counter[str]:
    policy = get_language_policy(language)
    supplemental_counts: Counter[str] = Counter()

    for chapter in chapters:
        normalized_text = policy.normalize_for_matching(chapter.text or "")
        if not normalized_text.strip():
            continue

        for match in _CJK_RUN_RE.finditer(normalized_text):
            token = match.group(0)
            if len(token) < 2:
                continue

            idx = 0
            token_len = len(token)
            while idx < token_len - 1:
                candidate = None
                for span_len in (4, 3, 2):
                    end_idx = idx + span_len
                    if end_idx > token_len:
                        continue
                    span = token[idx:end_idx]
                    if not looks_like_zh_person_name(span):
                        continue
                    match_candidate = policy.normalize_for_matching(span)
                    if span in common_words or match_candidate in common_words:
                        continue
                    candidate = span
                    break
                if candidate is None:
                    idx += 1
                    continue
                supplemental_counts[candidate] += 1
                idx += len(candidate)

    return Counter(
        {
            candidate: count
            for candidate, count in supplemental_counts.items()
            if count >= TEXT_FALLBACK_ZH_SPLIT_NAME_MIN_COUNT
        }
    )


def _merge_candidate_counters(
    primary: Counter[str],
    supplemental: Counter[str],
) -> Counter[str]:
    if not supplemental:
        return primary

    merged = Counter(primary)
    for candidate, count in supplemental.items():
        merged[candidate] = max(int(merged.get(candidate, 0)), int(count))
    return merged


def _merge_zh_person_name_shadow_candidates(
    candidate_counts: Counter[str],
) -> Counter[str]:
    if not candidate_counts:
        return candidate_counts

    merged = Counter(candidate_counts)
    for candidate, count in candidate_counts.items():
        canonical = strip_zh_person_name_trailing_noise(candidate)
        if canonical is None or canonical not in candidate_counts:
            continue
        if candidate == canonical or count <= 0:
            continue
        merged[canonical] += int(count)
        del merged[candidate]
    return merged


def _is_zh_fragment_token(token: str, *, common_words: set[str]) -> bool:
    return (
        bool(token)
        and len(token) <= TEXT_FALLBACK_ZH_FRAGMENT_MAX_TOKEN_CHARS
        and is_cjk_name_token(token)
        and token not in common_words
        and (
            looks_like_zh_translit_fragment(token) or is_zh_name_suffix_title(token)
        )
    )


def _recover_bound_zh_fragment_candidates(
    chapters: Sequence[ChapterText],
    *,
    language: str,
    common_words: set[str],
    candidate_counts: Counter[str],
) -> Counter[str]:
    policy = get_language_policy(language)
    pair_counts: Counter[tuple[str, str]] = Counter()
    outgoing_counts: Counter[str] = Counter()
    incoming_counts: Counter[str] = Counter()

    for chapter in chapters:
        chapter_text = chapter.text or ""
        if not chapter_text.strip():
            continue

        _, chapter_tokens = tokenize_text(chapter_text, language=language)
        previous_fragment = None
        for raw_token in chapter_tokens:
            token = policy.normalize_token(raw_token)
            if _is_zh_fragment_token(token, common_words=common_words):
                if previous_fragment is not None:
                    pair_counts[(previous_fragment, token)] += 1
                    outgoing_counts[previous_fragment] += 1
                    incoming_counts[token] += 1
                previous_fragment = token
            else:
                previous_fragment = None

    if not pair_counts:
        return candidate_counts

    best_successor: dict[str, tuple[str, int]] = {}
    best_predecessor: dict[str, tuple[str, int]] = {}
    ambiguous_successors: set[str] = set()
    ambiguous_predecessors: set[str] = set()

    for (left, right), count in pair_counts.items():
        if count < TEXT_FALLBACK_ZH_FRAGMENT_EXTENSION_MIN_COUNT:
            continue
        if count / max(int(outgoing_counts.get(left, 0)), 1) < TEXT_FALLBACK_ZH_FRAGMENT_DOMINANCE_THRESHOLD:
            continue
        if count / max(int(incoming_counts.get(right, 0)), 1) < TEXT_FALLBACK_ZH_FRAGMENT_DOMINANCE_THRESHOLD:
            continue

        successor = best_successor.get(left)
        if successor is None or count > successor[1]:
            best_successor[left] = (right, int(count))
            ambiguous_successors.discard(left)
        elif count == successor[1] and right != successor[0]:
            ambiguous_successors.add(left)

        predecessor = best_predecessor.get(right)
        if predecessor is None or count > predecessor[1]:
            best_predecessor[right] = (left, int(count))
            ambiguous_predecessors.discard(right)
        elif count == predecessor[1] and left != predecessor[0]:
            ambiguous_predecessors.add(right)

    recovered = Counter(candidate_counts)
    start_tokens = [
        left
        for left in best_successor
        if left not in ambiguous_successors
        and left not in best_predecessor
        and looks_like_zh_translit_fragment(left)
    ]
    if not start_tokens:
        return recovered

    for start in start_tokens:
        fragments = [start]
        chain_count = 2**31 - 1
        current = start
        seen = {start}

        while current in best_successor and current not in ambiguous_successors:
            if is_zh_name_suffix_title(current):
                break
            next_token, edge_count = best_successor[current]
            predecessor = best_predecessor.get(next_token)
            if (
                next_token in seen
                or next_token in ambiguous_predecessors
                or predecessor is None
                or predecessor[0] != current
            ):
                break
            fragments.append(next_token)
            chain_count = min(chain_count, int(edge_count))
            seen.add(next_token)
            current = next_token
            if is_zh_name_suffix_title(current):
                break

        if len(fragments) < 2:
            continue

        merged = "".join(fragments)
        if len(merged) < 3 or len(set(merged)) < 2 or merged in common_words:
            continue

        recovered[merged] = max(int(recovered.get(merged, 0)), int(chain_count))
        for fragment in fragments:
            if fragment not in recovered:
                continue
            remaining = int(recovered[fragment]) - int(chain_count)
            if remaining > 0:
                recovered[fragment] = remaining
            else:
                del recovered[fragment]

    return recovered


def _recover_zh_translit_name_spans(
    chapters: Sequence[ChapterText],
    *,
    language: str,
    common_words: set[str],
) -> Counter[str]:
    policy = get_language_policy(language)
    translit_chars = get_zh_translit_chars()
    suffix_titles = sorted(get_zh_name_suffix_titles(), key=lambda item: (-len(item), item))
    recovered: Counter[str] = Counter()

    for chapter in chapters:
        normalized_text = policy.normalize_for_matching(chapter.text or "")
        if not normalized_text.strip():
            continue

        for match in _CJK_RUN_RE.finditer(normalized_text):
            token = match.group(0)
            idx = 0
            token_len = len(token)
            while idx < token_len:
                if token[idx] not in translit_chars:
                    idx += 1
                    continue

                end_idx = idx
                while end_idx < token_len and token[end_idx] in translit_chars:
                    end_idx += 1

                stem = token[idx:end_idx]
                candidate = stem if len(stem) >= 3 else ""
                matched_title = ""
                if candidate:
                    for title in suffix_titles:
                        if token.startswith(title, end_idx):
                            candidate = stem + title
                            matched_title = title
                            break

                if not candidate:
                    idx += 1
                    continue

                match_candidate = policy.normalize_for_matching(candidate)
                if candidate in common_words or match_candidate in common_words:
                    idx += max(1, len(stem))
                    continue

                recovered[candidate] += 1
                idx = end_idx + len(matched_title)

    return recovered


def _looks_like_zh_translit_name_with_optional_title(token: str) -> bool:
    if looks_like_zh_translit_fragment(token):
        return True
    for title in get_zh_name_suffix_titles():
        if token.endswith(title):
            stem = token[: -len(title)]
            if len(stem) >= 3 and looks_like_zh_translit_fragment(stem):
                return True
    return False


def _suppress_zh_translit_fragment_candidates(
    candidate_counts: Counter[str],
) -> Counter[str]:
    if not candidate_counts:
        return candidate_counts

    cleaned = Counter(candidate_counts)
    recovered_names = [
        candidate
        for candidate in cleaned
        if len(candidate) >= 3 and _looks_like_zh_translit_name_with_optional_title(candidate)
    ]
    for full_name in recovered_names:
        full_count = int(cleaned.get(full_name, 0))
        if full_count <= 0:
            continue
        for candidate in list(cleaned):
            if candidate == full_name or len(candidate) >= len(full_name):
                continue
            if candidate not in full_name:
                continue
            if not (
                looks_like_zh_translit_fragment(candidate) or is_zh_name_suffix_title(candidate)
            ):
                continue
            if int(cleaned.get(candidate, 0)) <= full_count:
                del cleaned[candidate]
    return cleaned


def window_offsets(text_length: int, window_size: int, window_step: int) -> list[int]:
    if text_length <= 0:
        return []
    if text_length <= window_size:
        return [0]

    offsets = list(range(0, max(text_length - window_size + 1, 1), window_step))
    last_start = text_length - window_size
    if offsets and offsets[-1] != last_start:
        offsets.append(last_start)
    return offsets


def count_window_offsets(text_length: int, window_size: int, window_step: int) -> int:
    if text_length <= 0:
        return 0
    if text_length <= window_size:
        return 1

    last_start = text_length - window_size
    step = max(int(window_step or 0), 1)
    count = (last_start // step) + 1
    if last_start % step:
        count += 1
    return count


def count_text_fallback_windows(chapters: Sequence[ChapterText]) -> int:
    return sum(
        count_window_offsets(
            len(chapter.text or ""),
            TEXT_FALLBACK_WINDOW_SIZE,
            TEXT_FALLBACK_WINDOW_STEP,
        )
        for chapter in chapters
        if (chapter.text or "").strip()
    )


def resolve_text_fallback_window_threshold(total_windows: int) -> int:
    if total_windows <= 0:
        return 0
    min_window_count = (
        1
        if total_windows < TEXT_FALLBACK_MIN_WINDOW_COUNT
        else TEXT_FALLBACK_MIN_WINDOW_COUNT
    )
    ratio_threshold = math.ceil(total_windows * TEXT_FALLBACK_MIN_WINDOW_RATIO)
    return max(
        min_window_count,
        min(ratio_threshold, TEXT_FALLBACK_MAX_WINDOW_THRESHOLD),
    )


def resolve_text_fallback_shortlist_limit(limit: int) -> int:
    shortlist_limit = max(
        int(limit or 0) * TEXT_FALLBACK_CANDIDATE_MULTIPLIER,
        int(limit or 0),
        1,
    )
    return min(
        shortlist_limit,
        max(int(limit or 0), TEXT_FALLBACK_CANDIDATE_HARD_CAP),
    )


def _window_contains_candidate(
    window_text: str,
    candidate: str,
    *,
    match_key: str,
    policy,
) -> bool:
    if not candidate:
        return False
    if policy.family == "cjk":
        return candidate in window_text

    lowered_window_text = window_text.casefold()
    start = 0
    while True:
        match_start = lowered_window_text.find(match_key, start)
        if match_start < 0:
            return False
        match_end = match_start + len(match_key)
        if policy.match_has_word_boundaries(window_text, match_start, match_end):
            return True
        start = match_start + 1


def _build_cjk_candidate_automaton(
    candidates: Sequence[str],
    *,
    values_by_candidate: dict[str, int] | None = None,
):
    if ahocorasick is None:
        return None

    automaton = ahocorasick.Automaton()
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        automaton.add_word(
            candidate,
            candidate
            if values_by_candidate is None
            else values_by_candidate[candidate],
        )
    automaton.make_automaton()
    return automaton


def _collect_window_candidates(
    window_text: str,
    *,
    shortlisted_candidates: Sequence[str],
    match_keys: dict[str, str],
    policy,
    candidate_automaton,
) -> set[str]:
    if policy.family == "cjk" and candidate_automaton is not None:
        return {
            str(candidate) for _, candidate in candidate_automaton.iter(window_text)
        }

    return {
        candidate
        for candidate in shortlisted_candidates
        if _window_contains_candidate(
            window_text,
            candidate,
            match_key=match_keys[candidate],
            policy=policy,
        )
    }


def _iter_text_fallback_tokenize_batches(
    chapters: Sequence[ChapterText],
    *,
    max_batch_chars: int = TEXT_FALLBACK_TOKENIZE_BATCH_CHARS,
):
    batch_limit = max(int(max_batch_chars or 0), 1)
    batch_texts: list[str] = []
    batch_chars = 0

    for chapter in chapters:
        chapter_text = chapter.text or ""
        if not chapter_text:
            continue
        if batch_texts and batch_chars + len(chapter_text) > batch_limit:
            yield "\n\n".join(batch_texts)
            batch_texts = []
            batch_chars = 0
        batch_texts.append(chapter_text)
        batch_chars += len(chapter_text)

    if batch_texts:
        yield "\n\n".join(batch_texts)


def extract_rust_zh_sorted_candidates(
    chapters: Sequence[ChapterText],
    *,
    common_words: set[str],
    limit: int | None = None,
    rust_candidate_counter: RustZhCandidateCounter = count_rust_zh_candidates,
) -> list[tuple[str, int]] | None:
    rust_counts = rust_candidate_counter(
        chapters=chapters,
        common_words=tuple(common_words),
        max_batch_chars=TEXT_FALLBACK_TOKENIZE_BATCH_CHARS,
        limit=limit,
    )
    if rust_counts is None:
        return None
    return [(item.name, item.count) for item in rust_counts]


def extract_text_candidate_counts(
    chapters: Sequence[ChapterText],
    *,
    novel_language: str | None,
    common_words_dir: str,
    rust_candidate_counter: RustZhCandidateCounter = count_rust_zh_candidates,
) -> tuple[str, Counter[str]]:
    resolved_language = resolve_text_processing_language(novel_language)
    policy = get_language_policy(resolved_language)
    common_words = load_common_words(
        resolved_language,
        common_words_dir=common_words_dir,
    )
    if policy.base_language == "zh":
        rust_sorted_candidates = extract_rust_zh_sorted_candidates(
            chapters,
            common_words=common_words,
            limit=None,
            rust_candidate_counter=rust_candidate_counter,
        )
        if rust_sorted_candidates is not None:
            return resolved_language, Counter(
                {candidate: count for candidate, count in rust_sorted_candidates}
            )

    candidate_counts: Counter[str] = Counter()
    for batch_text in _iter_text_fallback_tokenize_batches(chapters):
        _, batch_tokens = tokenize_text(
            batch_text,
            language=resolved_language,
        )
        for token in batch_tokens:
            normalized = policy.normalize_token(token)
            if len(normalized) < 2:
                continue
            match_candidate = policy.normalize_for_matching(normalized)
            if normalized in common_words or match_candidate in common_words:
                continue
            candidate_counts[normalized] += 1
    if policy.base_language == "zh":
        candidate_counts = _merge_candidate_counters(
            candidate_counts,
            _count_likely_zh_split_names(
                chapters,
                language=resolved_language,
                common_words=common_words,
            ),
        )
        candidate_counts = _merge_candidate_counters(
            candidate_counts,
            _recover_zh_translit_name_spans(
                chapters,
                language=resolved_language,
                common_words=common_words,
            ),
        )
        candidate_counts = _recover_bound_zh_fragment_candidates(
            chapters,
            language=resolved_language,
            common_words=common_words,
            candidate_counts=candidate_counts,
        )
        candidate_counts = _suppress_zh_translit_fragment_candidates(candidate_counts)
        candidate_counts = _merge_zh_person_name_shadow_candidates(candidate_counts)
    return resolved_language, candidate_counts


def build_cjk_refinement_inputs_from_shortlist(
    chapters: Sequence[ChapterText],
    *,
    shortlisted_candidates: Sequence[str],
) -> tuple[tuple[str, ...], dict[str, int], dict[int, int], int] | None:
    if not shortlisted_candidates:
        return (), {}, {}, 0

    names_by_id = tuple(sorted(shortlisted_candidates))
    candidate_count = len(names_by_id)
    candidate_id_by_name = {
        candidate: candidate_id for candidate_id, candidate in enumerate(names_by_id)
    }
    candidate_automaton = _build_cjk_candidate_automaton(
        shortlisted_candidates,
        values_by_candidate=candidate_id_by_name,
    )
    if candidate_automaton is None:
        return None

    importance_counts = [0] * candidate_count
    pair_counts: dict[int, int] = {}
    seen_generations = [0] * candidate_count
    window_generation = 0
    total_windows = 0

    for chapter in chapters:
        chapter_text = chapter.text or ""
        if not chapter_text.strip():
            continue
        for start_pos in window_offsets(
            len(chapter_text),
            TEXT_FALLBACK_WINDOW_SIZE,
            TEXT_FALLBACK_WINDOW_STEP,
        ):
            total_windows += 1
            window_generation += 1
            end_pos = min(start_pos + TEXT_FALLBACK_WINDOW_SIZE, len(chapter_text))
            window_text = chapter_text[start_pos:end_pos]
            present_ids: list[int] = []
            for _, candidate_id in candidate_automaton.iter(window_text):
                if seen_generations[candidate_id] == window_generation:
                    continue
                seen_generations[candidate_id] = window_generation
                present_ids.append(candidate_id)
            if not present_ids:
                continue

            present_ids.sort()
            present_count = len(present_ids)
            for index, left_id in enumerate(present_ids):
                importance_counts[left_id] += 1
                row_offset = left_id * candidate_count
                for right_index in range(index + 1, present_count):
                    pair_key = row_offset + present_ids[right_index]
                    pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1

    if total_windows <= 0:
        return names_by_id, {}, {}, 0

    threshold = resolve_text_fallback_window_threshold(total_windows)
    included_mask = [count >= threshold for count in importance_counts]
    importance = {
        names_by_id[candidate_id]: count
        for candidate_id, count in enumerate(importance_counts)
        if included_mask[candidate_id]
    }
    if not importance:
        return names_by_id, {}, {}, total_windows

    included_pair_counts: dict[int, int] = {}
    for pair_key, count in pair_counts.items():
        if count <= 0:
            continue
        left_id, right_id = divmod(pair_key, candidate_count)
        if included_mask[left_id] and included_mask[right_id]:
            included_pair_counts[pair_key] = count

    return names_by_id, importance, included_pair_counts, total_windows


def build_refinement_inputs_from_text_candidates(
    chapters: Sequence[ChapterText],
    *,
    novel_language: str | None,
    common_words_dir: str,
    limit: int,
    rust_block_refinement_builder: RustZhBlockRefinementBuilder | None = None,
    rust_candidate_counter: RustZhCandidateCounter = count_rust_zh_candidates,
    rust_window_summarizer: RustZhWindowSummarizer = summarize_rust_zh_windows,
) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    result = _build_text_refinement_inputs_from_candidates(
        chapters,
        novel_language=novel_language,
        common_words_dir=common_words_dir,
        limit=limit,
        rust_block_refinement_builder=rust_block_refinement_builder,
        rust_candidate_counter=rust_candidate_counter,
        rust_window_summarizer=rust_window_summarizer,
    )
    return result.importance, result.cooccurrence_pairs


def _build_text_refinement_inputs_from_candidates(
    chapters: Sequence[ChapterText],
    *,
    novel_language: str | None,
    common_words_dir: str,
    limit: int,
    rust_block_refinement_builder: RustZhBlockRefinementBuilder | None = None,
    rust_candidate_counter: RustZhCandidateCounter = count_rust_zh_candidates,
    rust_window_summarizer: RustZhWindowSummarizer = summarize_rust_zh_windows,
) -> TextRefinementInputs:
    resolved_language = resolve_text_processing_language(novel_language)
    policy = get_language_policy(resolved_language)
    common_words = load_common_words(
        resolved_language,
        common_words_dir=common_words_dir,
    )
    if policy.base_language == "zh":
        rust_block_summary = (
            rust_block_refinement_builder or build_rust_zh_block_refinement_inputs
        )(
            chapters=chapters,
            common_words=tuple(common_words),
            limit=limit,
        )
        if rust_block_summary is not None:
            canonical_surfaces = {
                surface.strip()
                for surfaces in rust_block_summary.canonical_surfaces.values()
                for surface in surfaces
                if str(surface or "").strip()
            }
            supported_alias_candidates = {
                name.strip()
                for left, right, _ in rust_block_summary.cooccurrence_pairs
                for name in (left, right)
                if str(name or "").strip()
            }
            supported_alias_candidates.update(canonical_surfaces)
            return TextRefinementInputs(
                importance=rust_block_summary.importance,
                cooccurrence_pairs=rust_block_summary.cooccurrence_pairs,
                allowed_alias_candidates=frozenset(
                    {*rust_block_summary.importance, *canonical_surfaces}
                ),
                supported_alias_candidates=frozenset(supported_alias_candidates),
            )

    shortlist_limit = resolve_text_fallback_shortlist_limit(limit)
    sorted_candidates = (
        extract_rust_zh_sorted_candidates(
            chapters,
            common_words=common_words,
            limit=shortlist_limit,
            rust_candidate_counter=rust_candidate_counter,
        )
        if policy.base_language == "zh"
        else None
    )
    if sorted_candidates is None:
        _, candidate_counts = extract_text_candidate_counts(
            chapters,
            novel_language=resolved_language,
            common_words_dir=common_words_dir,
            rust_candidate_counter=rust_candidate_counter,
        )
        if not candidate_counts:
            return TextRefinementInputs(importance={}, cooccurrence_pairs=[])
        sorted_candidates = sorted(
            candidate_counts.items(),
            key=lambda item: (-item[1], -len(item[0]), item[0]),
        )
    if not sorted_candidates:
        return TextRefinementInputs(importance={}, cooccurrence_pairs=[])

    if policy.family == "whitespace":
        title_candidates = [
            (candidate, count)
            for candidate, count in sorted_candidates
            if candidate[:1].isupper()
        ]
        if title_candidates:
            sorted_candidates = title_candidates

    shortlisted_candidates = [
        candidate for candidate, _ in sorted_candidates[:shortlist_limit]
    ]
    if not shortlisted_candidates:
        return TextRefinementInputs(importance={}, cooccurrence_pairs=[])

    if policy.base_language == "zh":
        total_windows = count_text_fallback_windows(chapters)
        if total_windows <= 0:
            return TextRefinementInputs(importance={}, cooccurrence_pairs=[])
        threshold = resolve_text_fallback_window_threshold(total_windows)
        rust_summary = rust_window_summarizer(
            chapters=chapters,
            shortlisted_candidates=shortlisted_candidates,
            window_size=TEXT_FALLBACK_WINDOW_SIZE,
            window_step=TEXT_FALLBACK_WINDOW_STEP,
            threshold=threshold,
        )
        if rust_summary is not None:
            if not rust_summary.importance:
                return TextRefinementInputs(importance={}, cooccurrence_pairs=[])
            supported_alias_candidates = {
                name.strip()
                for left, right, _ in rust_summary.cooccurrence_pairs
                for name in (left, right)
                if str(name or "").strip()
            }
            return TextRefinementInputs(
                importance=rust_summary.importance,
                cooccurrence_pairs=rust_summary.cooccurrence_pairs,
                allowed_alias_candidates=frozenset(shortlisted_candidates),
                supported_alias_candidates=frozenset(supported_alias_candidates),
            )

    if policy.family == "cjk":
        cjk_result = build_cjk_refinement_inputs_from_shortlist(
            chapters,
            shortlisted_candidates=shortlisted_candidates,
        )
        if cjk_result is not None:
            candidate_names, importance, pair_counts, _ = cjk_result
            if not importance:
                return TextRefinementInputs(importance={}, cooccurrence_pairs=[])
            candidate_count = len(candidate_names)
            sorted_pair_counts = sorted(
                pair_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            cooccurrence_pairs = [
                (
                    candidate_names[left_id],
                    candidate_names[right_id],
                    count,
                )
                for pair_key, count in sorted_pair_counts
                for left_id, right_id in [divmod(pair_key, candidate_count)]
            ]
            supported_alias_candidates = {
                name.strip()
                for left, right, _ in cooccurrence_pairs
                for name in (left, right)
                if str(name or "").strip()
            }
            return TextRefinementInputs(
                importance=importance,
                cooccurrence_pairs=cooccurrence_pairs,
                allowed_alias_candidates=frozenset(shortlisted_candidates),
                supported_alias_candidates=frozenset(supported_alias_candidates),
            )

    match_keys = {
        candidate: policy.normalize_for_matching(candidate)
        for candidate in shortlisted_candidates
    }
    candidate_automaton = None

    importance_counter: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    total_windows = 0
    for chapter in chapters:
        chapter_text = chapter.text or ""
        if not chapter_text.strip():
            continue
        for start_pos in window_offsets(
            len(chapter_text),
            TEXT_FALLBACK_WINDOW_SIZE,
            TEXT_FALLBACK_WINDOW_STEP,
        ):
            total_windows += 1
            end_pos = min(start_pos + TEXT_FALLBACK_WINDOW_SIZE, len(chapter_text))
            window_text = chapter_text[start_pos:end_pos]
            present_names = _collect_window_candidates(
                window_text,
                shortlisted_candidates=shortlisted_candidates,
                match_keys=match_keys,
                policy=policy,
                candidate_automaton=candidate_automaton,
            )
            if not present_names:
                continue
            for name in present_names:
                importance_counter[name] += 1
            for left, right in combinations(sorted(present_names), 2):
                pair_counts[(left, right)] += 1

    if total_windows <= 0:
        return TextRefinementInputs(importance={}, cooccurrence_pairs=[])

    threshold = resolve_text_fallback_window_threshold(total_windows)
    importance = {
        name: count for name, count in importance_counter.items() if count >= threshold
    }
    if not importance:
        return TextRefinementInputs(importance={}, cooccurrence_pairs=[])

    cooccurrence_pairs = sorted(
        (
            (left, right, count)
            for (left, right), count in pair_counts.items()
            if count > 0 and left in importance and right in importance
        ),
        key=lambda item: (-item[2], item[0], item[1]),
    )
    supported_alias_candidates = {
        name.strip()
        for left, right, _ in cooccurrence_pairs
        for name in (left, right)
        if str(name or "").strip()
    }
    return TextRefinementInputs(
        importance=importance,
        cooccurrence_pairs=cooccurrence_pairs,
        allowed_alias_candidates=frozenset(shortlisted_candidates),
        supported_alias_candidates=frozenset(supported_alias_candidates),
    )


__all__ = [
    "TEXT_FALLBACK_CANDIDATE_HARD_CAP",
    "TEXT_FALLBACK_CANDIDATE_MULTIPLIER",
    "TEXT_FALLBACK_TOKENIZE_BATCH_CHARS",
    "TEXT_FALLBACK_WINDOW_SIZE",
    "TEXT_FALLBACK_WINDOW_STEP",
    "build_cjk_refinement_inputs_from_shortlist",
    "build_refinement_inputs_from_text_candidates",
    "count_text_fallback_windows",
    "count_window_offsets",
    "extract_rust_zh_sorted_candidates",
    "extract_text_candidate_counts",
    "resolve_text_fallback_shortlist_limit",
    "resolve_text_fallback_window_threshold",
    "window_offsets",
]
