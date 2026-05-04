import json
import io
import tarfile
import subprocess
from pathlib import Path

import scripts.loadtest.strict_hosted_beta_campaign as strict_campaign
from scripts.loadtest.strict_hosted_beta_campaign import (
    CampaignRunner,
    derive_seed,
    resolve_scenarios,
    summarize_guardrail_failures,
)


def test_resolve_scenarios_builds_three_repeats_and_preserves_two_user_mix(tmp_path: Path):
    matrix = {
        "repeats": 3,
        "mix_weights": [0.7, 0.2, 0.1],
        "scenarios": [
            {"name": "balanced-2", "profile": "balanced", "total_users": 2, "duration_seconds": 300}
        ],
    }
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    resolved = resolve_scenarios(matrix_path, repeats_override=None, base_seed=20260325)
    assert len(resolved) == 3
    assert [(item.writers, item.onboarding, item.world) for item in resolved] == [(1, 1, 0)] * 3
    assert [item.repeat_index for item in resolved] == [1, 2, 3]
    assert len({item.seed for item in resolved}) == 3


def test_derive_seed_is_deterministic():
    assert derive_seed(20260325, "balanced-2:1") == derive_seed(20260325, "balanced-2:1")
    assert derive_seed(20260325, "balanced-2:1") != derive_seed(20260325, "balanced-2:2")


def test_resolve_scenarios_preserves_open_loop_fields(tmp_path: Path):
    matrix = {
        "repeats": 1,
        "scenarios": [
            {
                "name": "continue-spam-1u",
                "runner": "open_loop",
                "open_loop_mode": "continue_spam",
                "profile": "surge",
                "total_users": 1,
                "duration_seconds": 120,
                "writers": 1,
                "onboarding": 0,
                "world": 0,
                "spam_writers": 1,
                "burst_size": 5,
                "burst_interval_seconds": 1.0,
            }
        ],
    }
    matrix_path = tmp_path / "matrix-open-loop.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    resolved = resolve_scenarios(matrix_path, repeats_override=None, base_seed=20260326)

    assert len(resolved) == 1
    assert resolved[0].runner == "open_loop"
    assert resolved[0].open_loop_mode == "continue_spam"
    assert resolved[0].spam_writers == 1
    assert resolved[0].burst_size == 5


def test_prepare_local_fixtures_copies_default_inputs(tmp_path: Path, monkeypatch):
    heavy_src = tmp_path / "source-heavy.txt"
    medium_src = tmp_path / "source-medium.txt"
    heavy_src.write_text("heavy fixture", encoding="utf-8")
    medium_src.write_text("medium fixture", encoding="utf-8")

    def fake_heavy(*, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(heavy_src.read_text(encoding="utf-8"), encoding="utf-8")
        return output_path

    def fake_medium(*, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(medium_src.read_text(encoding="utf-8"), encoding="utf-8")
        return output_path

    monkeypatch.setattr(strict_campaign, "ensure_heavy_upload_fixture", fake_heavy)
    monkeypatch.setattr(strict_campaign, "ensure_medium_upload_fixture", fake_medium)

    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "strict0325a-src",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    runner = CampaignRunner(args)

    fixtures = runner.prepare_local_fixtures()

    assert fixtures.heavy_upload.read_text(encoding="utf-8") == "heavy fixture"
    assert fixtures.medium_upload.read_text(encoding="utf-8") == "medium fixture"
    assert "_campaign-inputs/fixtures/heavy_upload.txt" in str(fixtures.heavy_upload)
    assert "_campaign-inputs/fixtures/medium_upload.txt" in str(fixtures.medium_upload)


def test_create_bundle_supports_raw_commit_refs(tmp_path: Path, monkeypatch):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "9aab2fd4e8cb82a0b0b55339527233c5eec55935",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)
    calls: list[list[str]] = []

    def fake_local(command, *, capture_output=True):
        calls.append(list(command))
        if command[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(command, 0, stdout="9aab2fd4e8cb\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runner, "local", fake_local)

    bundle_path = runner.create_bundle()

    assert bundle_path.name == "novwr.bundle"
    assert calls[0][:2] == ["git", "rev-parse"]
    assert calls[1][:2] == ["git", "update-ref"]
    assert calls[2][:3] == ["git", "bundle", "create"]
    assert calls[3][:3] == ["git", "update-ref", "-d"]


def test_start_remote_background_keeps_directory_setup_outside_async_job(tmp_path: Path, monkeypatch):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "strict0325a-src",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)
    captured: dict[str, str] = {}

    def fake_ssh(instance: str, command: str, *, capture_output: bool = True):
        captured["instance"] = instance
        captured["command"] = command
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr(runner, "ssh", fake_ssh)

    runner._start_remote_background(
        "lt-target",
        shell_command="echo ok",
        remote_log=Path("/home/omega/loadtest-artifacts/foo/run.log"),
        remote_pid=Path("/home/omega/loadtest-artifacts/foo/run.pid"),
        remote_status=Path("/home/omega/loadtest-artifacts/foo/run.status"),
    )

    command = captured["command"]
    assert captured["instance"] == "lt-target"
    assert "mkdir -p /home/omega/loadtest-artifacts/foo" in command
    assert "rm -f /home/omega/loadtest-artifacts/foo/run.log /home/omega/loadtest-artifacts/foo/run.pid /home/omega/loadtest-artifacts/foo/run.status" in command
    assert "; nohup bash -lc " in command
    assert "pid=$!;" in command
    assert "printf '%s' \"$pid\" > /home/omega/loadtest-artifacts/foo/run.pid" in command
    assert "& echo $!" not in command


def test_initialize_repo_uses_resolved_commit_when_source_ref_is_symbolic(tmp_path: Path, monkeypatch):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "HEAD",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)
    runner.source_commit = "9aab2fd4e8cb82a0b0b55339527233c5eec55935"
    captured: dict[str, str] = {}

    def fake_ssh(instance: str, command: str, *, capture_output: bool = True):
        captured["instance"] = instance
        captured["command"] = command
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr(runner, "ssh", fake_ssh)

    runner.initialize_repo("lt-target")

    assert captured["instance"] == "lt-target"
    assert "checkout --detach 9aab2fd4e8cb82a0b0b55339527233c5eec55935" in captured["command"]
    assert "checkout --detach HEAD" not in captured["command"]


def test_scp_from_recursive_extracts_into_requested_local_path(tmp_path: Path, monkeypatch):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "strict0325a-src",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)
    local_path = tmp_path / "scenario" / "generator-artifacts"
    remote_dir_name = "world-spam-1u-r1"
    real_run = subprocess.run
    calls = {"gcloud": 0}

    def fake_run(command, *run_args, **run_kwargs):
        if command[:3] == ["gcloud", "compute", "ssh"]:
            calls["gcloud"] += 1
            if calls["gcloud"] == 1:
                raise subprocess.CalledProcessError(255, command)
            stdout_handle = run_kwargs.get("stdout")
            assert stdout_handle is not None
            payload = io.BytesIO()
            with tarfile.open(fileobj=payload, mode="w") as tar:
                root = tarfile.TarInfo(name=remote_dir_name)
                root.type = tarfile.DIRTYPE
                root.mode = 0o755
                tar.addfile(root)
                content = b'{"result":"ok"}\n'
                info = tarfile.TarInfo(name=f"{remote_dir_name}/events.jsonl")
                info.size = len(content)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(content))
            stdout_handle.write(payload.getvalue())
            stdout_handle.flush()
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return real_run(command, *run_args, **run_kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner.scp_from("lt-target", f"/remote/{remote_dir_name}", local_path, recursive=True)

    assert (local_path / "events.jsonl").read_text(encoding="utf-8") == '{"result":"ok"}\n'
    assert not (local_path.parent / remote_dir_name).exists()
    assert calls["gcloud"] == 2


def test_capture_metadata_is_best_effort(tmp_path: Path, monkeypatch, capsys):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "strict0325a-src",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)

    def fake_ssh(instance: str, command: str, *, capture_output: bool = True):
        raise subprocess.CalledProcessError(255, ["gcloud", "compute", "ssh", instance])

    monkeypatch.setattr(runner, "ssh", fake_ssh)

    runner.capture_metadata("lt-target", Path("/tmp/meta.json"), services=["novwr"])

    captured = capsys.readouterr()
    assert "metadata capture failed on lt-target" in captured.out


def test_wait_for_remote_background_tolerates_transient_poll_error(tmp_path: Path, monkeypatch):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "strict0325a-src",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)
    calls = {"count": 0}

    def fake_ssh(instance: str, command: str, *, capture_output: bool = True):
        calls["count"] += 1
        if calls["count"] == 1:
            raise subprocess.CalledProcessError(255, ["gcloud", "compute", "ssh", instance])
        return subprocess.CompletedProcess([], 0, stdout="0\n", stderr="")

    monkeypatch.setattr(runner, "ssh", fake_ssh)

    runner._wait_for_remote_background(
        "lt-target",
        remote_status=Path("/tmp/status"),
        remote_log=Path("/tmp/log"),
        timeout_seconds=30,
        poll_seconds=0,
    )

    assert calls["count"] == 2


def test_summarize_guardrail_failures_reports_non_stable_scenarios():
    failures = summarize_guardrail_failures(
        {
            "continue-spam-1u": {
                "classification_counts": {"stable": 1},
            },
            "world-spam-1u": {
                "classification_counts": {"stable": 0, "beyond_stable": 1},
            },
        }
    )

    assert failures == ["world-spam-1u: beyond_stable=1"]


def test_ssh_retries_transient_connection_reset(tmp_path: Path, monkeypatch):
    args = strict_campaign.build_parser().parse_args(
        [
            "run",
            "--project",
            "p",
            "--zone",
            "z",
            "--source-ref",
            "strict0325a-src",
            "--env-file",
            str(tmp_path / "hosted.env"),
            "--invite-codes",
            str(tmp_path / "invite_codes.txt"),
            "--output-dir",
            str(tmp_path / "out"),
            "--allow-dirty-worktree",
        ]
    )
    runner = CampaignRunner(args)
    calls = {"count": 0}

    def fake_local(command, *, capture_output=True):
        calls["count"] += 1
        if calls["count"] == 1:
            exc = subprocess.CalledProcessError(255, command, output="")
            exc.stderr = "Connection reset by 1.2.3.4 port 22"
            raise exc
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(runner, "local", fake_local)

    result = runner.ssh("lt-target", "echo ok")

    assert result.stdout == "ok\n"
    assert calls["count"] == 2
