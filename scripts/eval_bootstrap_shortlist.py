from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any

try:
    import tiktoken
except ModuleNotFoundError:  # pragma: no cover - optional local dependency
    tiktoken = None

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings  # noqa: E402
from app.core.bootstrap_refinement import (  # noqa: E402
    _build_output_limit_instruction,
    _build_refinement_prompt,
    _select_refinement_prompt_shortlist,
)
from app.core.bootstrap_text_fallback import (  # noqa: E402
    _count_likely_zh_split_names,
    _merge_candidate_counters,
    build_refinement_inputs_from_text_candidates,
    count_text_fallback_windows,
    resolve_text_fallback_shortlist_limit,
    resolve_text_fallback_window_threshold,
)
from app.core.indexing.builder import (  # noqa: E402
    ChapterText,
    load_common_words,
    tokenize_text,
)
from app.core.indexing.state_proto_rust_text import summarize_rust_zh_windows  # noqa: E402
from app.core.ingest.parser_service import parse_source_file  # noqa: E402
from app.core.text import PromptKey, get_prompt  # noqa: E402
from app.language_policy import get_language_policy  # noqa: E402
from benchmarks.bootstrap_v1.shortlist_eval import (  # noqa: E402
    build_curve_metrics,
    evaluate_entity_shortlist,
    evaluate_pair_shortlist,
    load_gold_set,
    load_shortlist_benchmark,
)
from benchmarks.bootstrap_v1.span_block_prototype import (  # noqa: E402
    build_span_block_refinement_inputs,
)


def _load_chapters(file_path: Path) -> list[ChapterText]:
    parsed = parse_source_file(str(file_path), requested_language="zh")
    return [
        ChapterText(chapter_id=index, text=chapter.content)
        for index, chapter in enumerate(parsed.chapters, start=1)
        if (chapter.content or "").strip()
    ]


def _load_chapters_from_paths(file_paths: list[Path] | tuple[Path, ...]) -> list[ChapterText]:
    chapters: list[ChapterText] = []
    chapter_id = 1
    for file_path in file_paths:
        text = Path(file_path).read_text(encoding="utf-8").strip()
        if not text:
            continue
        chapters.append(ChapterText(chapter_id=chapter_id, text=text))
        chapter_id += 1
    return chapters


def _build_old_counts(chapters: list[ChapterText], *, common_words_dir: str) -> Counter[str]:
    policy = get_language_policy("zh")
    common_words = load_common_words("zh", common_words_dir=common_words_dir)
    counts: Counter[str] = Counter()
    for chapter in chapters:
        _, tokens = tokenize_text(chapter.text or "", language="zh")
        for token in tokens:
            normalized = policy.normalize_token(token)
            if len(normalized) < 2:
                continue
            match_candidate = policy.normalize_for_matching(normalized)
            if normalized in common_words or match_candidate in common_words:
                continue
            counts[normalized] += 1
    return _merge_candidate_counters(
        counts,
        _count_likely_zh_split_names(
            chapters,
            language="zh",
            common_words=common_words,
        ),
    )


def _build_old_inputs(
    chapters: list[ChapterText],
    *,
    common_words_dir: str,
    limit: int,
) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    counts = _build_old_counts(chapters, common_words_dir=common_words_dir)
    shortlist_limit = resolve_text_fallback_shortlist_limit(limit)
    sorted_candidates = sorted(
        counts.items(),
        key=lambda item: (-item[1], -len(item[0]), item[0]),
    )
    shortlisted = [name for name, _ in sorted_candidates[:shortlist_limit]]
    total_windows = count_text_fallback_windows(chapters)
    threshold = resolve_text_fallback_window_threshold(total_windows)
    summary = summarize_rust_zh_windows(
        chapters=chapters,
        shortlisted_candidates=shortlisted,
        window_size=500,
        window_step=250,
        threshold=threshold,
    )
    if summary is None:
        return {}, []
    return summary.importance, summary.cooccurrence_pairs


def _build_old_prompt(
    importance: dict[str, int],
    cooccurrence_pairs: list[tuple[str, str, int]],
) -> tuple[str, list[tuple[str, int]], list[tuple[str, str, int]]]:
    sorted_candidates = sorted(
        importance.items(),
        key=lambda item: (-item[1], -len(item[0]), item[0]),
    )[:180]
    keep = {name for name, _ in sorted_candidates}
    sorted_pairs = [
        (left, right, count)
        for left, right, count in cooccurrence_pairs
        if left in keep and right in keep
    ][:240]
    candidate_lines = (
        "\n".join(f"- {name}: {count}" for name, count in sorted_candidates)
        or "- (none)"
    )
    pair_lines = (
        "\n".join(f"- {left} -- {right}: {count}" for left, right, count in sorted_pairs)
        or "- (none)"
    )
    prompt = get_prompt(PromptKey.BOOTSTRAP_REFINEMENT, locale="zh").format(
        candidate_lines=candidate_lines,
        pair_lines=pair_lines,
    )
    prompt = (
        f"{prompt}\n\n"
        f"{_build_output_limit_instruction('zh', max_entities=80, max_relationships=120)}"
    )
    return prompt, sorted_candidates, sorted_pairs


def _build_shortlist_payload(
    *,
    importance: dict[str, int],
    pairs: list[tuple[str, str, int]],
    novel_language: str,
    prompt_locale: str = "zh",
) -> dict[str, Any]:
    candidates, prompt_pairs = _select_refinement_prompt_shortlist(
        importance,
        pairs,
        max_candidates=64,
        max_pairs=96,
        novel_language=novel_language,
    )
    prompt = _build_refinement_prompt(
        importance,
        pairs,
        max_candidates=64,
        max_pairs=96,
        max_entities=80,
        max_relationships=120,
        prompt_locale=prompt_locale,
        novel_language=novel_language,
    )
    return {
        "importance": importance,
        "pairs": pairs,
        "candidates": candidates,
        "prompt_pairs": prompt_pairs,
        "prompt": prompt,
    }


def _evaluate_with_gold(
    *,
    candidates: list[tuple[str, int]],
    pairs: list[tuple[str, str, int]],
    gold_dir: Path,
    novel_language: str,
    entity_topk: int,
    pair_topk: int,
    entity_curve_topks: list[int],
    pair_curve_topks: list[int],
) -> dict[str, Any]:
    gold = load_gold_set(gold_dir, novel_language=novel_language)
    curves = build_curve_metrics(
        candidates=candidates,
        pairs=pairs,
        gold=gold,
        entity_topks=entity_curve_topks,
        pair_topks=pair_curve_topks,
    )
    return {
        "entity": {
            "budget_topk": entity_topk,
            "at_budget": evaluate_entity_shortlist(candidates, gold, topk=entity_topk),
            "curve": curves["entity_curve"],
        },
        "pair": {
            "budget_topk": pair_topk,
            "at_budget": evaluate_pair_shortlist(pairs, gold, topk=pair_topk),
            "curve": curves["pair_curve"],
        },
    }


def _attach_method_report(
    *,
    result: dict[str, Any],
    label: str,
    payload: dict[str, Any],
    enc,
    gold_dir: Path | None,
    novel_language: str,
    entity_topk: int,
    pair_topk: int,
    entity_curve_topks: list[int],
    pair_curve_topks: list[int],
) -> None:
    result[f"{label}_prompt_tokens"] = (
        len(enc.encode(payload["prompt"])) if enc is not None else len(payload["prompt"])
    )
    result[f"{label}_candidates_top50"] = payload["candidates"][:50]
    result[f"{label}_pairs_top50"] = payload["prompt_pairs"][:50]
    if gold_dir is not None:
        result[f"{label}_metrics"] = _evaluate_with_gold(
            candidates=payload["candidates"],
            pairs=payload["prompt_pairs"],
            gold_dir=gold_dir,
            novel_language=novel_language,
            entity_topk=entity_topk,
            pair_topk=pair_topk,
            entity_curve_topks=entity_curve_topks,
            pair_curve_topks=pair_curve_topks,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate bootstrap shortlist quality on a local novel."
    )
    parser.add_argument("--benchmark", help="Benchmark JSON path with source_path or chapters_glob + gold_dir")
    parser.add_argument("--file", help="Override local novel file path")
    parser.add_argument("--gold-dir", help="Override gold directory with entities.tsv + pairs.tsv")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    benchmark = load_shortlist_benchmark(args.benchmark) if args.benchmark else None
    file_path = (
        Path(args.file).expanduser().resolve()
        if args.file
        else (benchmark.source_path if benchmark else None)
    )
    if file_path is None and not (benchmark and benchmark.chapter_paths):
        raise SystemExit("--file or --benchmark is required")

    gold_dir = (
        Path(args.gold_dir).expanduser().resolve()
        if args.gold_dir
        else (benchmark.gold_dir if benchmark else None)
    )
    novel_language = benchmark.novel_language if benchmark else "zh"

    settings = get_settings()
    enc = tiktoken.get_encoding("cl100k_base") if tiktoken is not None else None
    output_path = Path(args.output).expanduser().resolve() if args.output else None

    entity_topk = int((benchmark.budgets if benchmark else {}).get("entity_topk", 64))
    pair_topk = int((benchmark.budgets if benchmark else {}).get("pair_topk", 96))
    entity_curve_topks = list((benchmark.curves if benchmark else {}).get("entity_topk") or [16, 32, 64])
    pair_curve_topks = list((benchmark.curves if benchmark else {}).get("pair_topk") or [32, 64, 96, 128, 150])

    chapters = (
        _load_chapters(file_path)
        if file_path is not None
        else _load_chapters_from_paths(benchmark.chapter_paths if benchmark else ())
    )
    old_importance, old_pairs = _build_old_inputs(
        chapters,
        common_words_dir=settings.bootstrap_common_words_dir,
        limit=settings.bootstrap_max_candidates,
    )
    new_importance, new_pairs = build_refinement_inputs_from_text_candidates(
        chapters,
        novel_language=novel_language,
        common_words_dir=settings.bootstrap_common_words_dir,
        limit=settings.bootstrap_max_candidates,
    )
    prototype_result = build_span_block_refinement_inputs(
        chapters,
        novel_language=novel_language,
        common_words_dir=settings.bootstrap_common_words_dir,
        limit=settings.bootstrap_max_candidates,
    )

    old_prompt, old_candidates, old_prompt_pairs = _build_old_prompt(old_importance, old_pairs)
    new_payload = _build_shortlist_payload(
        importance=new_importance,
        pairs=new_pairs,
        novel_language=novel_language,
    )
    prototype_payload = _build_shortlist_payload(
        importance=prototype_result.importance,
        pairs=prototype_result.cooccurrence_pairs,
        novel_language=novel_language,
    )

    result: dict[str, Any] = {
        "file": str(file_path) if file_path is not None else None,
        "chapter_files": [str(path) for path in (benchmark.chapter_paths if benchmark else ())],
        "chapter_count": len(chapters),
        "char_count": sum(len(chapter.text or "") for chapter in chapters),
        "prompt_tokenizer": "cl100k_base" if enc is not None else "char_fallback",
        "prototype_canonical_surfaces": {
            canonical: list(surfaces)
            for canonical, surfaces in prototype_result.canonical_surfaces.items()
        },
    }
    if benchmark is not None:
        result["benchmark"] = {
            "book_id": benchmark.book_id,
            "book_name": benchmark.book_name,
            "novel_language": benchmark.novel_language,
            "gold_dir": str(benchmark.gold_dir),
            "budgets": benchmark.budgets,
            "curves": benchmark.curves,
            "notes": list(benchmark.notes),
        }

    result["old_prompt_tokens"] = len(enc.encode(old_prompt)) if enc is not None else len(old_prompt)
    result["old_candidates_top50"] = old_candidates[:50]
    result["old_pairs_top50"] = old_prompt_pairs[:50]
    if gold_dir is not None:
        result["old_metrics"] = _evaluate_with_gold(
            candidates=old_candidates,
            pairs=old_prompt_pairs,
            gold_dir=gold_dir,
            novel_language=novel_language,
            entity_topk=entity_topk,
            pair_topk=pair_topk,
            entity_curve_topks=entity_curve_topks,
            pair_curve_topks=pair_curve_topks,
        )

    _attach_method_report(
        result=result,
        label="new",
        payload=new_payload,
        enc=enc,
        gold_dir=gold_dir,
        novel_language=novel_language,
        entity_topk=entity_topk,
        pair_topk=pair_topk,
        entity_curve_topks=entity_curve_topks,
        pair_curve_topks=pair_curve_topks,
    )
    _attach_method_report(
        result=result,
        label="prototype",
        payload=prototype_payload,
        enc=enc,
        gold_dir=gold_dir,
        novel_language=novel_language,
        entity_topk=entity_topk,
        pair_topk=pair_topk,
        entity_curve_topks=entity_curve_topks,
        pair_curve_topks=pair_curve_topks,
    )

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(output_path)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
