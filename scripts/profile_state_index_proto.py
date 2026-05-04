from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.state_index_v1 import (
    StateProtoCase,
    build_state_proto_reference_cases,
    get_state_proto_profiling_targets,
)

from app.core.ingest.parser_service import parse_source_file
from app.core.indexing.builder import ChapterText
from app.core.indexing.state_proto_executor import execute_state_proto_build
from app.core.indexing.state_proto_runtime import StateProtoIndex


def _format_table(rows: list[dict[str, object]], case_rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No profile rows generated."

    headers = [
        "slug",
        "index_kind",
        "target_scope",
        "chapters",
        "chars",
        "build_ms",
        "payload_bytes",
        "rss_kib",
        "peak_rss_kib",
        "target_count",
        "discover_targets_ms",
        "segment_count",
        "mention_posting_count",
        "claim_atom_count",
        "coverage_rep_count",
        "state_case_passes",
        "state_case_total",
        "budget_pass",
        "provenance_pass",
    ]
    widths = {
        header: max(len(header), *[len(str(row.get(header, ""))) for row in rows])
        for header in headers
    }
    profile_lines = [
        " ".join(header.ljust(widths[header]) for header in headers),
        " ".join("-" * widths[header] for header in headers),
    ]
    for row in rows:
        profile_lines.append(
            " ".join(str(row.get(header, "")).ljust(widths[header]) for header in headers)
        )

    if not case_rows:
        return "\n".join(profile_lines)

    case_headers = [
        "case_id",
        "language",
        "slot",
        "expected_value",
        "state_proto_v2_value",
        "state_proto_v2_pass",
        "expected_uncertainty_hint",
        "uncertainty_hint",
        "uncertainty_hint_pass",
        "budget_pass",
        "provenance_pass",
    ]
    case_widths = {
        header: max(len(header), *[len(str(row.get(header, ""))) for row in case_rows])
        for header in case_headers
    }
    case_lines = [
        "",
        "Fixture case comparison",
        " ".join(header.ljust(case_widths[header]) for header in case_headers),
        " ".join("-" * case_widths[header] for header in case_headers),
    ]
    for row in case_rows:
        case_lines.append(
            " ".join(str(row.get(header, "")).ljust(case_widths[header]) for header in case_headers)
        )
    return "\n".join([*profile_lines, *case_lines])


def _iter_real_file_paths(*, files: list[str], input_dir: str | None, glob_pattern: str) -> list[Path]:
    resolved_paths: list[Path] = []
    for raw_path in files:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Benchmark input file not found: {raw_path}")
        resolved_paths.append(path)

    if input_dir:
        root = Path(input_dir).expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Benchmark input directory not found: {input_dir}")
        resolved_paths.extend(
            sorted(path.resolve() for path in root.glob(glob_pattern) if path.is_file())
        )

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in resolved_paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _load_chapter_dir(dir_path: str) -> tuple[str, list[ChapterText]]:
    root = Path(dir_path).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Chapter directory not found: {dir_path}")
    chapter_files = sorted(path for path in root.glob("*.txt") if path.is_file())
    if not chapter_files:
        raise FileNotFoundError(f"No chapter .txt files found in: {dir_path}")
    chapters = [
        ChapterText(chapter_id=index, text=path.read_text(encoding="utf-8"))
        for index, path in enumerate(chapter_files, start=1)
    ]
    if root.name == "chapters" and root.parent.name:
        return root.parent.name, chapters
    return root.name, chapters


def _build_profile_rows_for_corpus(
    *,
    slug: str,
    chapters: list[ChapterText],
    requested_language: str | None,
    case_summary: dict[str, object],
) -> list[dict[str, object]]:
    chapter_chars = sum(len(chapter.text or "") for chapter in chapters)
    rows: list[dict[str, object]] = []

    explicit_targets = get_state_proto_profiling_targets(slug)
    if explicit_targets:
        explicit_output = execute_state_proto_build(
            chapters=chapters,
            novel_language=requested_language,
            target_specs=explicit_targets,
        )
        rows.append(
            {
                "slug": slug,
                "index_kind": "state_proto_v2",
                "target_scope": "explicit_targets",
                "chapters": len(chapters),
                "chars": chapter_chars,
                "build_ms": explicit_output.duration_ms,
                "payload_bytes": explicit_output.payload_bytes,
                "rss_kib": explicit_output.rss_kib,
                "peak_rss_kib": explicit_output.peak_rss_kib,
                "target_count": explicit_output.target_count,
                "discover_targets_ms": explicit_output.discover_targets_ms,
                "segment_count": explicit_output.segment_count,
                "mention_posting_count": explicit_output.mention_posting_count,
                "claim_atom_count": explicit_output.claim_atom_count,
                "coverage_rep_count": explicit_output.coverage_rep_count,
                "state_case_passes": case_summary["state_proto_passes"],
                "state_case_total": case_summary["total"],
                "budget_pass": case_summary["budget_pass"],
                "provenance_pass": case_summary["provenance_pass"],
            }
        )

    return rows


def _estimate_case_budget_and_provenance(case: StateProtoCase) -> dict[str, object]:
    chapters = [
        ChapterText(chapter_id=index, text=text)
        for index, text in enumerate(case.chapters, start=1)
    ]
    output = execute_state_proto_build(
        chapters=chapters,
        novel_language=case.novel_language,
        target_specs=case.target_specs,
    )
    index = StateProtoIndex.from_msgpack(output.index_payload)
    packs = index.find_state(case.query_target_id, case.query_slot)
    if not packs:
        return {
            "state_proto_v2_value": None,
            "uncertainty_hint": None,
            "budget_pass": False,
            "provenance_pass": False,
        }

    primary_pack = packs[0]
    primary_source = index.open(primary_pack.primary_handle)
    trace_payload = index.open(primary_pack.trace_handle)
    provenance = index.resolve_pack_provenance(primary_pack)

    payload_budget = (
        index.estimate_payload_tokens(packs)
        + index.estimate_payload_tokens(primary_source)
        + index.estimate_payload_tokens(trace_payload)
    )
    if primary_pack.conflict_handle:
        payload_budget += index.estimate_payload_tokens(index.open(primary_pack.conflict_handle))

    return {
        "state_proto_v2_value": primary_pack.candidate_value_signature,
        "uncertainty_hint": primary_pack.uncertainty_hint,
        "budget_pass": payload_budget <= 3000,
        "provenance_pass": (
            provenance.primary_claim.value_signature == primary_pack.candidate_value_signature
            and provenance.segment.segment_id == provenance.primary_claim.segment_id
            and provenance.source_payload.chapter_id == provenance.segment.chapter_id
        ),
    }


def _build_case_rows() -> tuple[list[dict[str, object]], dict[str, object]]:
    case_rows: list[dict[str, object]] = []
    total = 0
    passes = 0
    uncertainty_hint_passes = 0
    budget_pass = True
    provenance_pass = True
    for case in build_state_proto_reference_cases():
        result = _estimate_case_budget_and_provenance(case)
        state_case_pass = result["state_proto_v2_value"] == case.expected_value
        uncertainty_hint_pass = result["uncertainty_hint"] == case.expected_hint
        total += 1
        passes += int(state_case_pass)
        uncertainty_hint_passes += int(uncertainty_hint_pass)
        budget_pass = budget_pass and bool(result["budget_pass"])
        provenance_pass = provenance_pass and bool(result["provenance_pass"])
        case_rows.append(
            {
                "case_id": case.case_id,
                "language": case.novel_language,
                "slot": case.query_slot,
                "expected_value": case.expected_value,
                "state_proto_v2_value": result["state_proto_v2_value"],
                "state_proto_v2_pass": state_case_pass,
                "expected_uncertainty_hint": case.expected_hint,
                "uncertainty_hint": result["uncertainty_hint"],
                "uncertainty_hint_pass": uncertainty_hint_pass,
                "budget_pass": result["budget_pass"],
                "provenance_pass": result["provenance_pass"],
            }
        )
    return case_rows, {
        "state_proto_passes": passes,
        "uncertainty_hint_passes": uncertainty_hint_passes,
        "total": total,
        "budget_pass": budget_pass,
        "provenance_pass": provenance_pass,
    }


def _profile_real_file_rows(
    *,
    file_paths: list[Path],
    requested_language: str | None,
    case_summary: dict[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in file_paths:
        parsed = parse_source_file(
            str(path),
            requested_language=requested_language,
        )
        chapters = [
            ChapterText(chapter_id=index, text=chapter.content)
            for index, chapter in enumerate(parsed.chapters, start=1)
            if (chapter.content or "").strip()
        ]
        rows.extend(
            _build_profile_rows_for_corpus(
                slug=path.name,
                chapters=chapters,
                requested_language=parsed.resolved_language,
                case_summary=case_summary,
            )
        )
    return rows


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices={"table", "json"}, default="table")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--input-dir")
    parser.add_argument("--glob", default="*.txt")
    parser.add_argument("--chapter-dir")
    parser.add_argument("--requested-language")
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    case_rows, case_summary = _build_case_rows()
    profile_rows: list[dict[str, object]] = []

    if args.chapter_dir:
        slug, chapters = _load_chapter_dir(args.chapter_dir)
        profile_rows.extend(
            _build_profile_rows_for_corpus(
                slug=slug,
                chapters=chapters,
                requested_language=args.requested_language,
                case_summary=case_summary,
            )
        )

    real_file_paths = _iter_real_file_paths(
        files=args.files,
        input_dir=args.input_dir,
        glob_pattern=args.glob,
    )
    if real_file_paths:
        profile_rows.extend(
            _profile_real_file_rows(
                file_paths=real_file_paths,
                requested_language=args.requested_language,
                case_summary=case_summary,
            )
        )

    if args.format == "json":
        print(
            json.dumps(
                {
                    "profile_rows": profile_rows,
                    "case_rows": case_rows,
                    "summary": case_summary,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(_format_table(profile_rows, case_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
