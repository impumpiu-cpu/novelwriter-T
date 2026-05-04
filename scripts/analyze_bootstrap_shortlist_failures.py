from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings  # noqa: E402
from app.core.bootstrap_refinement import _select_refinement_prompt_shortlist  # noqa: E402
from app.core.bootstrap_text_fallback import build_refinement_inputs_from_text_candidates  # noqa: E402
from app.core.indexing.builder import ChapterText, load_common_words  # noqa: E402
from app.core.indexing.state_proto_rust_text import (  # noqa: E402
    build_rust_zh_block_refinement_inputs,
    count_rust_zh_candidates,
)
from app.core.ingest.parser_service import parse_source_file  # noqa: E402
from app.language_policy import get_language_policy  # noqa: E402
from benchmarks.bootstrap_v1.shortlist_eval import (  # noqa: E402
    load_gold_set,
    load_shortlist_benchmark,
    normalize_pair_ids,
)

DISCOVERY_MULTIPLIER = 8
DISCOVERY_HARD_CAP = 2048


@dataclass(slots=True)
class EntityFailureRow:
    entity_id: str
    canonical_name: str
    entity_type: str
    importance_tier: int
    category: str
    prompt_surfaces: list[str]
    raw_surfaces: list[str]
    seed_surfaces: list[str]
    recoverable_extensions: list[dict[str, Any]]


@dataclass(slots=True)
class PairFailureRow:
    src_entity_id: str
    tgt_entity_id: str
    src_canonical_name: str
    tgt_canonical_name: str
    pair_type: str
    importance_tier: int
    category: str
    prompt_pair_surfaces: list[list[str]]
    raw_pair_surfaces: list[list[str]]
    prompt_endpoint_present: bool
    raw_endpoint_present: bool


@dataclass(slots=True)
class BookFailureReport:
    book_id: str
    book_name: str
    entity_metrics: dict[str, Any]
    pair_metrics: dict[str, Any]
    entity_category_counts: dict[str, int]
    pair_category_counts: dict[str, int]
    entity_failures: list[EntityFailureRow]
    pair_failures: list[PairFailureRow]


def _load_chapters(benchmark) -> list[ChapterText]:
    if benchmark.source_path is not None:
        parsed = parse_source_file(str(benchmark.source_path), requested_language=benchmark.novel_language)
        return [
            ChapterText(chapter_id=index, text=chapter.content)
            for index, chapter in enumerate(parsed.chapters, start=1)
            if (chapter.content or "").strip()
        ]
    chapters: list[ChapterText] = []
    chapter_id = 1
    for file_path in benchmark.chapter_paths:
        text = Path(file_path).read_text(encoding="utf-8").strip()
        if not text:
            continue
        chapters.append(ChapterText(chapter_id=chapter_id, text=text))
        chapter_id += 1
    return chapters


def _normalize_surface(surface: str, *, novel_language: str) -> str:
    policy = get_language_policy(novel_language, sample_text=surface or None)
    return policy.normalize_for_matching(str(surface or "").strip())


def _map_surface_scores_to_gold_ids(
    surface_items: list[tuple[str, int]], *, gold, novel_language: str
) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for surface, score in surface_items:
        entity_id = gold.alias_to_entity_id.get(
            _normalize_surface(surface, novel_language=novel_language)
        )
        if entity_id is None:
            continue
        mapped[entity_id].append({"surface": surface, "score": int(score)})
    return dict(mapped)


def _map_pair_scores_to_gold_keys(
    pair_items: list[tuple[str, str, int]], *, gold, novel_language: str
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    mapped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for left, right, score in pair_items:
        left_id = gold.alias_to_entity_id.get(
            _normalize_surface(left, novel_language=novel_language)
        )
        right_id = gold.alias_to_entity_id.get(
            _normalize_surface(right, novel_language=novel_language)
        )
        if not left_id or not right_id or left_id == right_id:
            continue
        key = normalize_pair_ids(left_id, right_id)
        if key not in gold.pair_by_key:
            continue
        mapped[key].append({"left": left, "right": right, "score": int(score)})
    return dict(mapped)


def _surface_recoverable_extensions(
    surfaces: tuple[str, ...], *, seed_names: set[str]
) -> list[dict[str, Any]]:
    recoverable: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for surface in surfaces:
        char_len = len(surface)
        for removed_chars in (1, 2):
            if char_len <= removed_chars:
                continue
            prefix_seed = surface[:-removed_chars]
            suffix_seed = surface[removed_chars:]
            if prefix_seed in seed_names:
                key = (surface, "suffix_extension", prefix_seed, removed_chars)
                if key not in seen:
                    seen.add(key)
                    recoverable.append(
                        {
                            "surface": surface,
                            "direction": "suffix_extension",
                            "seed": prefix_seed,
                            "removed_chars": removed_chars,
                        }
                    )
            if suffix_seed in seed_names:
                key = (surface, "prefix_extension", suffix_seed, removed_chars)
                if key not in seen:
                    seen.add(key)
                    recoverable.append(
                        {
                            "surface": surface,
                            "direction": "prefix_extension",
                            "seed": suffix_seed,
                            "removed_chars": removed_chars,
                        }
                    )
    return recoverable


def _classify_entity_failure(
    entity, *, prompt_matches, raw_matches, seed_matches, recoverable_extensions
) -> str:
    if prompt_matches:
        matched_surfaces = {item["surface"] for item in prompt_matches}
        if entity.canonical_name in matched_surfaces:
            return "matched_prompt_canonical"
        return "matched_prompt_alias"
    if raw_matches:
        return "prompt_ranking_miss"
    if seed_matches:
        return "seed_present_builder_drop"
    if recoverable_extensions:
        return "possible_local_extension_miss"
    return "seed_discovery_miss"



def _classify_pair_failure(
    *,
    prompt_pair_matches: list[dict[str, Any]],
    raw_pair_matches: list[dict[str, Any]],
    prompt_endpoint_present: bool,
    raw_endpoint_present: bool,
) -> str:
    if prompt_pair_matches:
        return "matched_prompt_pair"
    if raw_pair_matches:
        return "prompt_pair_ranking_miss"
    if prompt_endpoint_present:
        return "pair_evidence_miss"
    if raw_endpoint_present:
        return "pair_endpoint_prompt_miss"
    return "pair_endpoint_builder_miss"



def _build_book_report(benchmark_path: Path) -> BookFailureReport:
    benchmark = load_shortlist_benchmark(benchmark_path)
    chapters = _load_chapters(benchmark)
    settings = get_settings()
    common_words = tuple(
        load_common_words(benchmark.novel_language, common_words_dir=settings.bootstrap_common_words_dir)
    )
    discovery_limit = min(
        max(int(benchmark.budgets["entity_topk"]) * DISCOVERY_MULTIPLIER, 1024),
        DISCOVERY_HARD_CAP,
    )
    seed_counts = count_rust_zh_candidates(
        chapters=chapters,
        common_words=common_words,
        max_batch_chars=256 * 1024,
        limit=discovery_limit,
    ) or []
    build_rust_zh_block_refinement_inputs(
        chapters=chapters,
        common_words=common_words,
        limit=int(benchmark.budgets["entity_topk"]),
    )
    importance, cooccurrence_pairs = build_refinement_inputs_from_text_candidates(
        chapters,
        novel_language=benchmark.novel_language,
        common_words_dir=settings.bootstrap_common_words_dir,
        limit=int(benchmark.budgets["entity_topk"]),
    )
    prompt_candidates, prompt_pairs = _select_refinement_prompt_shortlist(
        importance,
        cooccurrence_pairs,
        max_candidates=int(benchmark.budgets["entity_topk"]),
        max_pairs=int(benchmark.budgets["pair_topk"]),
        novel_language=benchmark.novel_language,
    )
    gold = load_gold_set(benchmark.gold_dir, novel_language=benchmark.novel_language)

    prompt_entity_matches = _map_surface_scores_to_gold_ids(
        [(name, int(score)) for name, score in prompt_candidates],
        gold=gold,
        novel_language=benchmark.novel_language,
    )
    raw_entity_matches = _map_surface_scores_to_gold_ids(
        sorted(importance.items(), key=lambda item: (-item[1], -len(item[0]), item[0])),
        gold=gold,
        novel_language=benchmark.novel_language,
    )
    seed_entity_matches = _map_surface_scores_to_gold_ids(
        [(item.name, int(item.count)) for item in seed_counts],
        gold=gold,
        novel_language=benchmark.novel_language,
    )
    prompt_pair_matches = _map_pair_scores_to_gold_keys(
        [(left, right, int(score)) for left, right, score in prompt_pairs],
        gold=gold,
        novel_language=benchmark.novel_language,
    )
    raw_pair_matches = _map_pair_scores_to_gold_keys(
        [(left, right, int(score)) for left, right, score in cooccurrence_pairs],
        gold=gold,
        novel_language=benchmark.novel_language,
    )

    prompt_entity_ids = set(prompt_entity_matches)
    raw_entity_ids = set(raw_entity_matches)
    seed_names = {item.name for item in seed_counts}

    entity_failures: list[EntityFailureRow] = []
    entity_category_counts: Counter[str] = Counter()
    for entity in gold.entities:
        prompt_matches = prompt_entity_matches.get(entity.entity_id, [])
        raw_matches = raw_entity_matches.get(entity.entity_id, [])
        seed_matches = seed_entity_matches.get(entity.entity_id, [])
        recoverable_extensions = _surface_recoverable_extensions(
            entity.surfaces,
            seed_names=seed_names,
        )
        category = _classify_entity_failure(
            entity,
            prompt_matches=prompt_matches,
            raw_matches=raw_matches,
            seed_matches=seed_matches,
            recoverable_extensions=recoverable_extensions,
        )
        entity_category_counts[category] += 1
        if category.startswith("matched_"):
            continue
        entity_failures.append(
            EntityFailureRow(
                entity_id=entity.entity_id,
                canonical_name=entity.canonical_name,
                entity_type=entity.entity_type,
                importance_tier=entity.importance_tier,
                category=category,
                prompt_surfaces=[item["surface"] for item in prompt_matches],
                raw_surfaces=[item["surface"] for item in raw_matches[:8]],
                seed_surfaces=[item["surface"] for item in seed_matches[:8]],
                recoverable_extensions=recoverable_extensions[:8],
            )
        )

    pair_failures: list[PairFailureRow] = []
    pair_category_counts: Counter[str] = Counter()
    for pair in gold.pairs:
        prompt_matches = prompt_pair_matches.get(pair.key, [])
        raw_matches = raw_pair_matches.get(pair.key, [])
        prompt_endpoint_present = (
            pair.src_entity_id in prompt_entity_ids and pair.tgt_entity_id in prompt_entity_ids
        )
        raw_endpoint_present = (
            pair.src_entity_id in raw_entity_ids and pair.tgt_entity_id in raw_entity_ids
        )
        category = _classify_pair_failure(
            prompt_pair_matches=prompt_matches,
            raw_pair_matches=raw_matches,
            prompt_endpoint_present=prompt_endpoint_present,
            raw_endpoint_present=raw_endpoint_present,
        )
        pair_category_counts[category] += 1
        if category == "matched_prompt_pair":
            continue
        pair_failures.append(
            PairFailureRow(
                src_entity_id=pair.src_entity_id,
                tgt_entity_id=pair.tgt_entity_id,
                src_canonical_name=gold.entity_by_id[pair.src_entity_id].canonical_name,
                tgt_canonical_name=gold.entity_by_id[pair.tgt_entity_id].canonical_name,
                pair_type=pair.pair_type,
                importance_tier=pair.importance_tier,
                category=category,
                prompt_pair_surfaces=[[item["left"], item["right"]] for item in prompt_matches[:6]],
                raw_pair_surfaces=[[item["left"], item["right"]] for item in raw_matches[:6]],
                prompt_endpoint_present=prompt_endpoint_present,
                raw_endpoint_present=raw_endpoint_present,
            )
        )

    entity_metrics = {
        "gold_count": len(gold.entities),
        "matched_count": entity_category_counts["matched_prompt_canonical"]
        + entity_category_counts["matched_prompt_alias"],
        "matched_prompt_alias": entity_category_counts["matched_prompt_alias"],
        "matched_prompt_canonical": entity_category_counts["matched_prompt_canonical"],
    }
    pair_metrics = {
        "gold_count": len(gold.pairs),
        "matched_count": pair_category_counts["matched_prompt_pair"],
    }

    return BookFailureReport(
        book_id=benchmark.book_id,
        book_name=benchmark.book_name,
        entity_metrics=entity_metrics,
        pair_metrics=pair_metrics,
        entity_category_counts=dict(entity_category_counts),
        pair_category_counts=dict(pair_category_counts),
        entity_failures=entity_failures,
        pair_failures=pair_failures,
    )



def _report_to_json_payload(reports: list[BookFailureReport]) -> dict[str, Any]:
    entity_totals: Counter[str] = Counter()
    pair_totals: Counter[str] = Counter()
    for report in reports:
        entity_totals.update(report.entity_category_counts)
        pair_totals.update(report.pair_category_counts)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "books": [
            {
                "book_id": report.book_id,
                "book_name": report.book_name,
                "entity_metrics": report.entity_metrics,
                "pair_metrics": report.pair_metrics,
                "entity_category_counts": report.entity_category_counts,
                "pair_category_counts": report.pair_category_counts,
                "entity_failures": [asdict(item) for item in report.entity_failures],
                "pair_failures": [asdict(item) for item in report.pair_failures],
            }
            for report in reports
        ],
        "cross_book_summary": {
            "entity_category_counts": dict(entity_totals),
            "pair_category_counts": dict(pair_totals),
        },
    }



def _report_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bootstrap shortlist failure taxonomy (current)",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        "## Cross-book summary",
        "",
        "### Entity categories",
        "",
    ]
    for name, count in sorted(
        payload["cross_book_summary"]["entity_category_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "### Pair categories", ""])
    for name, count in sorted(
        payload["cross_book_summary"]["pair_category_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        lines.append(f"- `{name}`: {count}")

    for book in payload["books"]:
        lines.extend([
            "",
            f"## {book['book_id']} — {book['book_name']}",
            "",
            f"- entity matched: {book['entity_metrics']['matched_count']} / {book['entity_metrics']['gold_count']}",
            f"- pair matched: {book['pair_metrics']['matched_count']} / {book['pair_metrics']['gold_count']}",
            "",
            "### Entity miss categories",
            "",
        ])
        for name, count in sorted(book["entity_category_counts"].items(), key=lambda item: (-item[1], item[0])):
            if name.startswith("matched_"):
                continue
            lines.append(f"- `{name}`: {count}")
        lines.extend(["", "### Top entity misses", ""])
        for item in book["entity_failures"][:15]:
            lines.append(
                f"- `{item['canonical_name']}` ({item['entity_type']}) -> `{item['category']}`"
                f" | raw={item['raw_surfaces'][:3]} | seed={item['seed_surfaces'][:3]}"
            )
        lines.extend(["", "### Pair miss categories", ""])
        for name, count in sorted(book["pair_category_counts"].items(), key=lambda item: (-item[1], item[0])):
            if name == "matched_prompt_pair":
                continue
            lines.append(f"- `{name}`: {count}")
        lines.extend(["", "### Top pair misses", ""])
        for item in book["pair_failures"][:12]:
            lines.append(
                f"- `{item['src_canonical_name']} -- {item['tgt_canonical_name']}` -> `{item['category']}`"
                f" | raw_pair={item['raw_pair_surfaces'][:2]} | endpoints(raw/prompt)=({item['raw_endpoint_present']}/{item['prompt_endpoint_present']})"
            )

    return "\n".join(lines) + "\n"



def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze reusable bootstrap shortlist failure classes.")
    parser.add_argument(
        "--benchmarks",
        nargs="*",
        default=[
            "benchmarks/bootstrap_v1/benchmarks/gmzz.shortlist.json",
            "benchmarks/bootstrap_v1/benchmarks/santi.shortlist.json",
            "benchmarks/bootstrap_v1/benchmarks/yxs.shortlist.json",
        ],
    )
    parser.add_argument(
        "--output-json",
        default="benchmarks/bootstrap_v1/eval_cards/current_failure_taxonomy.json",
    )
    parser.add_argument(
        "--output-md",
        default="benchmarks/bootstrap_v1/eval_cards/current_failure_taxonomy.md",
    )
    args = parser.parse_args()

    reports = [_build_book_report((ROOT_DIR / path).resolve()) for path in args.benchmarks]
    payload = _report_to_json_payload(reports)

    output_json = (ROOT_DIR / args.output_json).resolve()
    output_md = (ROOT_DIR / args.output_md).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(_report_to_markdown(payload), encoding="utf-8")

    print(f"wrote {output_json}")
    print(f"wrote {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
