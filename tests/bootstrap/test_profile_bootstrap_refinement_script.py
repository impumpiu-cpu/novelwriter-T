from __future__ import annotations

from pathlib import Path

import scripts.profile_bootstrap_refinement as profile_script


def test_profile_bootstrap_refinement_parser_defaults():
    parser = profile_script._build_arg_parser()

    args = parser.parse_args([])

    assert args.format == "table"
    assert args.repeat == 1
    assert args.sample_interval_ms == 5
    assert args.stages == list(profile_script.DEFAULT_STAGES)


def test_aggregate_rows_summarizes_repeats():
    rows = [
        {
            "file": "demo.txt",
            "stage": "parse",
            "duration_ms": 10.0,
            "rss_delta_kib": 100,
            "peak_rss_delta_kib": 140,
            "resolved_language": "zh",
            "chapter_count": 2,
            "chapter_chars": 123,
        },
        {
            "file": "demo.txt",
            "stage": "parse",
            "duration_ms": 14.0,
            "rss_delta_kib": 120,
            "peak_rss_delta_kib": 180,
            "resolved_language": "zh",
            "chapter_count": 2,
            "chapter_chars": 123,
        },
    ]

    aggregated = profile_script.aggregate_rows(rows)

    assert aggregated == [
        {
            "file": "demo.txt",
            "stage": "parse",
            "repeats": 2,
            "duration_ms_avg": 12.0,
            "duration_ms_p50": 12.0,
            "duration_ms_max": 14.0,
            "rss_delta_kib_avg": 110.0,
            "rss_delta_kib_max": 120,
            "peak_rss_delta_kib_avg": 160.0,
            "peak_rss_delta_kib_max": 180,
            "details": "lang=zh chapters=2 chars=123",
            "resolved_language": "zh",
            "chapter_count": 2,
            "chapter_chars": 123,
            "candidate_count": None,
            "shortlisted_count": None,
            "shortlist_limit": None,
            "total_windows": None,
            "threshold": None,
            "importance_count": None,
            "pair_count": None,
        }
    ]


def test_run_stage_once_parse_reports_basic_metrics(tmp_path: Path):
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text(
        "第一章\n林秋在云港司守夜。\n\n第二章\n顾衡来找林秋。\n",
        encoding="utf-8",
    )

    row = profile_script.run_stage_once(
        file_path=novel_path,
        stage="parse",
        requested_language="zh",
        limit=20,
        sample_interval_ms=1,
    )

    assert row["file"] == "novel.txt"
    assert row["stage"] == "parse"
    assert row["resolved_language"] == "zh"
    assert row["chapter_count"] == 2
    assert row["chapter_chars"] > 0
    assert row["duration_ms"] >= 0
    assert row["peak_rss_kib"] is None or row["peak_rss_kib"] >= 0


def test_run_stage_once_window_summary_skips_non_zh(tmp_path: Path):
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text(
        "Chapter 1\nAlice met Bob in Paris.\n\nChapter 2\nBob left London.\n",
        encoding="utf-8",
    )

    row = profile_script.run_stage_once(
        file_path=novel_path,
        stage="window_summary",
        requested_language="en",
        limit=20,
        sample_interval_ms=1,
    )

    assert row["file"] == "novel.txt"
    assert row["stage"] == "window_summary"
    assert row["skipped"] is True
    assert row["skip_reason"] == "window_summary_only_supported_for_zh"
