from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
import app.core.derived_assets.jobs as derived_asset_jobs_module
from app.core.indexing import lifecycle as lifecycle_module
from app.core.indexing import (
    STATE_PROTO_EXECUTOR_BACKEND_RUST,
    WINDOW_INDEX_STATUS_FAILED,
    WINDOW_INDEX_STATUS_FRESH,
    enqueue_window_index_rebuild_for_latest_revision,
    enqueue_window_index_rebuild_job,
    inspect_window_index_rebuild_job,
    mark_window_index_inputs_changed,
    run_next_window_index_rebuild_job,
)
from app.database import Base
from app.models import Chapter, DerivedAssetJob, Novel


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_novel_with_text(db):
    novel = Novel(title="T", author="A", file_path="/tmp/test.txt")
    db.add(novel)
    db.commit()
    db.refresh(novel)
    db.add(
        Chapter(
            novel_id=novel.id,
            chapter_number=1,
            title="One",
            content="Alice met Bob in the city.",
        )
    )
    db.commit()
    db.refresh(novel)
    return novel


def _enqueue_and_run_latest_revision(novel_id: int) -> None:
    assert (
        enqueue_window_index_rebuild_for_latest_revision(
            novel_id,
            session_factory=TestingSessionLocal,
        )
        is not None
    )
    assert run_next_window_index_rebuild_job(session_factory=TestingSessionLocal) is True


def _assert_window_index_metrics(job: DerivedAssetJob) -> None:
    metrics = dict((job.result or {}).get("metrics") or {})
    assert metrics["full_build_ms"] >= 0
    assert metrics["load_chapters_ms"] >= 0
    assert metrics["payload_bytes"] > 0
    assert metrics["chapter_count"] == 1
    assert metrics["chapter_chars"] > 0
    assert metrics["build_artifacts_ms"] >= 0
    assert metrics["serialize_ms"] >= 0
    assert metrics["persist_ms"] >= 0
    assert "peak_rss_kib" in metrics
    assert metrics["index_backend"] == "state_proto_v2"
    assert metrics["executor_backend"] == STATE_PROTO_EXECUTOR_BACKEND_RUST
    assert metrics["target_count"] >= 0
    assert metrics["segment_count"] > 0
    assert metrics["plan_mode"] in {"full", "incremental", "reuse_existing"}


def test_enqueue_window_index_job_coalesces_duplicate_triggers(db):
    novel = _create_novel_with_text(db)

    revision_one = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=revision_one,
    )
    db.commit()

    revision_two = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=revision_two,
    )
    db.commit()

    jobs = db.query(DerivedAssetJob).all()
    assert len(jobs) == 1
    assert jobs[0].status == "queued"
    assert jobs[0].target_revision == 2
    assert jobs[0].completed_revision is None

    snapshot = inspect_window_index_rebuild_job(db, novel_id=novel.id)
    assert snapshot is not None
    assert snapshot.status == "queued"
    assert snapshot.target_revision == 2


def test_window_index_job_reclaims_stale_running_row(db):
    novel = _create_novel_with_text(db)
    target_revision = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=target_revision,
    )
    db.commit()

    job = db.query(DerivedAssetJob).filter(DerivedAssetJob.novel_id == novel.id).first()
    assert job is not None
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    job.status = "running"
    job.claimed_revision = target_revision
    job.lease_owner = "stale-owner"
    job.lease_expires_at = stale_time
    job.started_at = stale_time
    db.commit()

    _enqueue_and_run_latest_revision(novel.id)

    db.refresh(novel)
    db.refresh(job)
    assert novel.window_index_status == WINDOW_INDEX_STATUS_FRESH
    assert novel.window_index_built_revision == target_revision
    assert job.status == "completed"
    assert job.completed_revision == target_revision
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.finished_at is not None
    _assert_window_index_metrics(job)


def test_window_index_job_failure_is_recoverable(db, monkeypatch):
    novel = _create_novel_with_text(db)
    target_revision = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=target_revision,
    )
    db.commit()

    original_build = lifecycle_module.WINDOW_INDEX_JOB_ADAPTER.build

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        lifecycle_module.WINDOW_INDEX_JOB_ADAPTER,
        "build",
        _raise,
    )

    _enqueue_and_run_latest_revision(novel.id)

    job = db.query(DerivedAssetJob).filter(DerivedAssetJob.novel_id == novel.id).first()
    assert job is not None
    db.refresh(novel)
    assert novel.window_index_status == WINDOW_INDEX_STATUS_FAILED
    assert job.status == "failed"
    assert job.error == "窗口索引重建失败，请稍后重试"

    monkeypatch.setattr(
        lifecycle_module.WINDOW_INDEX_JOB_ADAPTER,
        "build",
        original_build,
    )
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=int(novel.window_index_revision or 0),
    )
    db.commit()

    _enqueue_and_run_latest_revision(novel.id)

    db.refresh(novel)
    db.refresh(job)
    assert novel.window_index_status == WINDOW_INDEX_STATUS_FRESH
    assert novel.window_index_built_revision == target_revision
    assert novel.window_index_error is None
    assert job.status == "completed"
    assert job.completed_revision == target_revision
    assert job.error is None
    _assert_window_index_metrics(job)


def test_window_index_job_advances_target_when_inputs_change_mid_build(db, monkeypatch):
    novel = _create_novel_with_text(db)
    target_revision = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=target_revision,
    )
    db.commit()

    original_build = lifecycle_module.execute_state_proto_build
    calls = {"count": 0}

    def _build(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            update_db = TestingSessionLocal()
            try:
                current = update_db.get(Novel, novel.id)
                assert current is not None
                mark_window_index_inputs_changed(current)
                update_db.commit()
            finally:
                update_db.close()
        return original_build(*args, **kwargs)

    monkeypatch.setattr(lifecycle_module, "execute_state_proto_build", _build)

    _enqueue_and_run_latest_revision(novel.id)

    job = db.query(DerivedAssetJob).filter(DerivedAssetJob.novel_id == novel.id).first()
    assert job is not None
    db.refresh(novel)
    db.refresh(job)
    assert calls["count"] == 2
    assert novel.window_index_status == WINDOW_INDEX_STATUS_FRESH
    assert novel.window_index_revision == 2
    assert novel.window_index_built_revision == 2
    assert job.status == "completed"
    assert job.target_revision == 2
    assert job.completed_revision == 2
    _assert_window_index_metrics(job)


def test_window_index_job_preserves_last_success_metrics_when_requeued(db):
    novel = _create_novel_with_text(db)

    _enqueue_and_run_latest_revision(novel.id)
    db.refresh(novel)

    job = db.query(DerivedAssetJob).filter(DerivedAssetJob.novel_id == novel.id).first()
    assert job is not None
    assert job.status == "completed"
    assert job.finished_at is not None
    first_finished_at = job.finished_at
    first_result = dict(job.result or {})
    _assert_window_index_metrics(job)

    revision_two = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=revision_two,
    )
    db.commit()

    db.refresh(job)
    assert job.status == "queued"
    assert job.completed_revision == 1
    assert job.finished_at == first_finished_at
    assert job.result == first_result


def test_window_index_job_reuses_last_success_payload_as_incremental_base(db, monkeypatch):
    novel = _create_novel_with_text(db)
    lifecycle_module.mark_window_index_build_succeeded(
        novel,
        index_payload=b"old-index",
        revision=1,
    )
    db.commit()

    target_revision = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=target_revision,
    )
    db.commit()

    seen_existing_payloads: list[bytes | None] = []
    original_build = lifecycle_module.execute_state_proto_build

    def _build(*args, **kwargs):
        seen_existing_payloads.append(kwargs.get("existing_payload"))
        return original_build(*args, **kwargs)

    monkeypatch.setattr(lifecycle_module, "execute_state_proto_build", _build)

    _enqueue_and_run_latest_revision(novel.id)

    assert seen_existing_payloads == [b"old-index"]


def test_window_index_job_refreshes_lease_during_long_build(db, monkeypatch):
    novel = _create_novel_with_text(db)
    target_revision = mark_window_index_inputs_changed(novel)
    enqueue_window_index_rebuild_job(
        db,
        novel_id=novel.id,
        target_revision=target_revision,
    )
    db.commit()

    original_build = lifecycle_module.execute_state_proto_build
    original_refresh = derived_asset_jobs_module._refresh_derived_asset_job_lease
    heartbeat_calls = {"count": 0}

    def _build(*args, **kwargs):
        time.sleep(1.2)
        return original_build(*args, **kwargs)

    def _refresh(*args, **kwargs):
        heartbeat_calls["count"] += 1
        return original_refresh(*args, **kwargs)

    monkeypatch.setattr(lifecycle_module, "execute_state_proto_build", _build)
    monkeypatch.setattr(derived_asset_jobs_module, "_refresh_derived_asset_job_lease", _refresh)

    assert (
        run_next_window_index_rebuild_job(
            session_factory=TestingSessionLocal,
            settings=Settings(
                derived_asset_job_lease_seconds=3,
                derived_asset_job_stale_timeout_seconds=30,
            ),
        )
        is True
    )

    job = db.query(DerivedAssetJob).filter(DerivedAssetJob.novel_id == novel.id).first()
    assert job is not None
    db.refresh(job)
    assert job.status == "completed"
    assert heartbeat_calls["count"] >= 1
