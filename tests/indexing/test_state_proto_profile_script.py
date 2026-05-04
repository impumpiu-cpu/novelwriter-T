from __future__ import annotations

from types import SimpleNamespace

import scripts.profile_state_index_proto as profile_script


def test_build_case_rows_surfaces_runtime_uncertainty_hint(monkeypatch):
    case = SimpleNamespace(
        case_id="hint_mismatch",
        novel_language="zh",
        query_slot="entity.current_location",
        expected_value="云港司",
        expected_hint="low_margin",
    )

    monkeypatch.setattr(
        profile_script,
        "build_state_proto_reference_cases",
        lambda: [case],
    )
    monkeypatch.setattr(
        profile_script,
        "_estimate_case_budget_and_provenance",
        lambda _case: {
            "state_proto_v2_value": "云港司",
            "uncertainty_hint": "fresh_conflict",
            "budget_pass": True,
            "provenance_pass": True,
        },
    )

    case_rows, summary = profile_script._build_case_rows()

    assert case_rows == [
        {
            "case_id": "hint_mismatch",
            "language": "zh",
            "slot": "entity.current_location",
            "expected_value": "云港司",
            "state_proto_v2_value": "云港司",
            "state_proto_v2_pass": True,
            "expected_uncertainty_hint": "low_margin",
            "uncertainty_hint": "fresh_conflict",
            "uncertainty_hint_pass": False,
            "budget_pass": True,
            "provenance_pass": True,
        }
    ]
    assert summary == {
        "state_proto_passes": 1,
        "uncertainty_hint_passes": 0,
        "total": 1,
        "budget_pass": True,
        "provenance_pass": True,
    }


def test_build_profile_rows_use_explicit_targets_only(monkeypatch):
    monkeypatch.setattr(
        profile_script,
        "get_state_proto_profiling_targets",
        lambda slug: ("target",) if slug == "demo" else (),
    )
    monkeypatch.setattr(
        profile_script,
        "execute_state_proto_build",
        lambda **kwargs: SimpleNamespace(
            duration_ms=12.3,
            payload_bytes=456,
            rss_kib=789,
            peak_rss_kib=987,
            target_count=2,
            discover_targets_ms=0.0,
            segment_count=5,
            mention_posting_count=4,
            claim_atom_count=3,
            coverage_rep_count=2,
        ),
    )

    rows = profile_script._build_profile_rows_for_corpus(
        slug="demo",
        chapters=[
            SimpleNamespace(chapter_id=1, text="第一章"),
            SimpleNamespace(chapter_id=2, text="第二章"),
        ],
        requested_language="zh",
        case_summary={
            "state_proto_passes": 1,
            "total": 1,
            "budget_pass": True,
            "provenance_pass": True,
        },
    )

    assert rows == [
        {
            "slug": "demo",
            "index_kind": "state_proto_v2",
            "target_scope": "explicit_targets",
            "chapters": 2,
            "chars": 6,
            "build_ms": 12.3,
            "payload_bytes": 456,
            "rss_kib": 789,
            "peak_rss_kib": 987,
            "target_count": 2,
            "discover_targets_ms": 0.0,
            "segment_count": 5,
            "mention_posting_count": 4,
            "claim_atom_count": 3,
            "coverage_rep_count": 2,
            "state_case_passes": 1,
            "state_case_total": 1,
            "budget_pass": True,
            "provenance_pass": True,
        }
    ]


def test_profile_script_parser_drops_auto_discovery_flags():
    parser = profile_script._build_arg_parser()

    args = parser.parse_args([])

    assert args.format == "table"
    assert not hasattr(args, "discovered_target_limit")
    assert not hasattr(args, "target_mode")
    assert not hasattr(args, "discovery_experiment")
