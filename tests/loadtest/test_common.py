from scripts.loadtest.common import (
    aggregate_repeat_summaries,
    allocate_mix,
    classify_run,
    percentile,
    summarize_events,
    summarize_monitor_samples,
)


def test_allocate_mix_uses_largest_remainder_without_losing_total():
    assert allocate_mix(11, (0.7, 0.2, 0.1)) == [8, 2, 1]


def test_percentile_interpolates_middle_values():
    assert percentile([1, 2, 3, 4], 50) == 2.5


def test_classify_run_marks_memory_danger_as_beyond_stable():
    assert classify_run(
        continuation_ttft_p95_s=3.2,
        continuation_error_rate=0.0,
        upload_chapters_p95_s=80.0,
        upload_bootstrap_p95_s=200.0,
        memory_danger=True,
    ) == "beyond_stable"


def test_classify_run_marks_open_loop_semantic_duplicates_as_beyond_stable():
    assert classify_run(
        continuation_ttft_p95_s=3.2,
        continuation_error_rate=0.0,
        upload_chapters_p95_s=80.0,
        upload_bootstrap_p95_s=200.0,
        memory_danger=False,
        open_loop_continuation_multi_accept_burst_rate=0.0,
        open_loop_continuation_duplicate_accept_count=0.0,
        open_loop_world_duplicate_accept_count=1.0,
        open_loop_bootstrap_duplicate_accept_count=0.0,
    ) == "beyond_stable"


def test_classify_run_allows_clean_open_loop_semantic_probe_without_ttft():
    assert classify_run(
        continuation_ttft_p95_s=None,
        continuation_error_rate=0.0,
        upload_chapters_p95_s=None,
        upload_bootstrap_p95_s=None,
        memory_danger=False,
        open_loop_continuation_multi_accept_burst_rate=0.0,
        open_loop_continuation_duplicate_accept_count=0.0,
        open_loop_world_duplicate_accept_count=0.0,
        open_loop_bootstrap_duplicate_accept_count=0.0,
        has_open_loop_semantic_probe=True,
    ) == "stable"


def test_summarize_monitor_samples_detects_memory_danger_and_service_metrics():
    summary = summarize_monitor_samples(
        [
            {
                "cpu_percent": 50.0,
                "memory_used_percent": 88.0,
                "loadavg_1": 1.2,
                "window_index_jobs": {"queued": 1, "running": 1},
                "repo_git_head": "abc123",
                "repo_git_branch": "HEAD",
                "repo_git_dirty": False,
                "services": {
                    "novwr": {
                        "state": "active",
                        "cpu_percent": 10.0,
                        "rss_mib": 128.0,
                        "thread_count": 8,
                        "open_fds": 40,
                    }
                },
            },
            {
                "cpu_percent": 95.0,
                "memory_used_percent": 93.5,
                "loadavg_1": 2.8,
                "window_index_jobs": {"queued": 3, "running": 1},
                "services": {
                    "novwr": {
                        "state": "active",
                        "cpu_percent": 30.0,
                        "rss_mib": 256.0,
                        "thread_count": 12,
                        "open_fds": 60,
                    }
                },
            },
        ]
    )
    assert summary["memory_danger"] is True
    assert summary["cpu_p95_percent"] == 92.75
    assert summary["repo_git_head"] == "abc123"
    assert summary["services"]["novwr"]["rss_p95_mib"] == 249.6


def test_summarize_events_tracks_busy_errors_and_bootstrap_waits():
    summary = summarize_events(
        [
            {
                "operation": "continuation_stream",
                "result": "error",
                "status_code": 503,
                "elapsed_s": 1.0,
                "error_code": "server_busy",
            },
            {
                "operation": "continuation_stream",
                "result": "ok",
                "status_code": 200,
                "elapsed_s": 10.0,
                "ttft_s": 6.0,
            },
            {
                "operation": "upload_and_wait",
                "result": "ok",
                "status_code": 202,
                "elapsed_s": 40.0,
                "chapters_ready_s": 3.0,
                "bootstrap_ready_s": 35.0,
                "bootstrap_llm_wait_s": 7.5,
            },
        ]
    )
    continuation = summary["operations"]["continuation_stream"]
    upload = summary["operations"]["upload_and_wait"]
    assert continuation["busy_error_count"] == 1
    assert continuation["busy_error_rate"] == 0.5
    assert upload["bootstrap_llm_wait_p95_s"] == 7.5


def test_summarize_events_tracks_open_loop_duplicate_accepts():
    summary = summarize_events(
        [
            {
                "operation": "continuation_stream_open_loop",
                "burst_id": "c-1",
                "accepted": True,
                "result": "ok",
                "status_code": 200,
                "elapsed_s": 8.0,
                "ttft_s": 4.0,
            },
            {
                "operation": "continuation_stream_open_loop",
                "burst_id": "c-1",
                "accepted": True,
                "result": "ok",
                "status_code": 200,
                "elapsed_s": 9.0,
                "ttft_s": 4.5,
            },
            {
                "operation": "continuation_stream_open_loop",
                "burst_id": "c-2",
                "accepted": False,
                "result": "error",
                "status_code": 503,
                "elapsed_s": 1.0,
                "error_code": "server_busy",
            },
            {
                "operation": "bootstrap_trigger_open_loop",
                "burst_id": "b-1",
                "accepted": True,
                "result": "ok",
                "status_code": 202,
                "elapsed_s": 0.3,
            },
            {
                "operation": "bootstrap_trigger_open_loop",
                "burst_id": "b-1",
                "accepted": False,
                "result": "error",
                "status_code": 409,
                "elapsed_s": 0.2,
                "error_code": "bootstrap_job_active",
            },
        ]
    )

    continuation = summary["open_loop"]["continuation_stream_open_loop"]
    bootstrap = summary["open_loop"]["bootstrap_trigger_open_loop"]
    assert continuation["burst_count"] == 2
    assert continuation["multi_accept_burst_count"] == 1
    assert continuation["duplicate_accept_count"] == 1
    assert continuation["multi_accept_burst_rate"] == 0.5
    assert bootstrap["duplicate_accept_count"] == 0
    assert summary["classification"] == "beyond_stable"


def test_aggregate_repeat_summaries_tracks_worst_repeat_values():
    aggregated = aggregate_repeat_summaries(
        [
            {
                "classification": "stable",
                "operations": {
                    "continuation_stream": {"ttft_p95_s": 4.0, "latency_p95_s": 20.0, "busy_error_rate": 0.0},
                    "upload_and_wait": {
                        "bootstrap_ready_p95_s": 40.0,
                        "bootstrap_llm_wait_p95_s": 5.0,
                        "chapters_ready_p95_s": 3.0,
                        "busy_error_rate": 0.0,
                    },
                    "chapter_update_and_wait": {"index_ready_p95_s": 6.0},
                },
                "open_loop": {
                    "continuation_stream_open_loop": {
                        "multi_accept_burst_rate": 0.0,
                        "duplicate_accept_count": 0,
                    },
                    "world_generate_open_loop": {
                        "duplicate_accept_count": 0,
                    },
                },
                "monitor": {"cpu_p95_percent": 20.0, "memory_used_p95_percent": 70.0},
            },
            {
                "classification": "beyond_stable",
                "operations": {
                    "continuation_stream": {"ttft_p95_s": 8.0, "latency_p95_s": 30.0, "busy_error_rate": 0.1},
                    "upload_and_wait": {
                        "bootstrap_ready_p95_s": 60.0,
                        "bootstrap_llm_wait_p95_s": 9.0,
                        "chapters_ready_p95_s": 5.0,
                        "busy_error_rate": 0.0,
                    },
                    "chapter_update_and_wait": {"index_ready_p95_s": 10.0},
                },
                "open_loop": {
                    "continuation_stream_open_loop": {
                        "multi_accept_burst_rate": 0.5,
                        "duplicate_accept_count": 3,
                    },
                    "world_generate_open_loop": {
                        "duplicate_accept_count": 2,
                    },
                },
                "monitor": {"cpu_p95_percent": 35.0, "memory_used_p95_percent": 75.0},
            },
        ]
    )
    assert aggregated["repeat_count"] == 2
    assert aggregated["classification_counts"] == {"stable": 1, "beyond_stable": 1}
    assert aggregated["metrics"]["continuation_ttft_p95_s"]["worst"] == 8.0
    assert aggregated["metrics"]["upload_bootstrap_llm_wait_p95_s"]["median"] == 7.0
    assert aggregated["metrics"]["open_loop_continuation_multi_accept_burst_rate"]["worst"] == 0.5
    assert aggregated["metrics"]["open_loop_world_duplicate_accept_count"]["median"] == 1.0
