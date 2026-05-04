# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, defer

from app.config import get_settings
from app.core.auth import get_current_user_or_default
from app.core.events import ensure_project_start_event, record_event
from app.core.ingest import (
    accept_novel_upload,
    inspect_novel_ingest_job,
    inspect_novel_readiness,
    reset_novel_ingest_job_for_retry,
)
from app.core.indexing.lifecycle import inspect_window_index_lifecycle
from app.database import get_db
from app.models import Novel, User
from app.schemas import (
    NovelResponse,
    UploadResponse,
)

from . import novel_support

router = APIRouter(prefix="/api/novels", tags=["novels"])


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_novel(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(""),
    language: str | None = Form(None),
    source_surface: str | None = Form(None),
    consent_acknowledged: bool = Form(False),
    consent_version: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    """Accept a novel upload and enqueue background ingest."""
    started_at = time.perf_counter()
    settings = get_settings()
    if not consent_acknowledged:
        raise HTTPException(
            status_code=400,
            detail={"code": "upload_consent_required", "message": "Upload consent is required"},
        )
    if consent_version != novel_support.UPLOAD_CONSENT_VERSION:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "upload_consent_version_mismatch",
                "message": "Upload consent version is outdated",
            },
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"code": "upload_filename_missing", "message": "No filename provided"},
        )

    allowed_extensions = {".txt"}
    original_name = file.filename.replace("\\", "/").split("/")[-1]
    ext = Path(original_name).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "upload_type_not_supported",
                "message": f"File type not supported. Allowed: {allowed_extensions}",
            },
        )

    stem = Path(original_name).stem
    safe_stem = "".join(c for c in stem if c.isalnum() or c in "._-").strip("._-")
    safe_stem = safe_stem[:80]
    token = uuid4().hex
    safe_filename = f"{safe_stem}_{token}{ext}" if safe_stem else f"{token}{ext}"
    file_path = novel_support.UPLOAD_DIR / safe_filename
    max_size = max(1, int(settings.upload_max_megabytes)) * 1024 * 1024
    chunk_size = max(1024, int(settings.upload_chunk_size_bytes))
    bytes_written = 0
    try:
        with file_path.open("wb") as handle:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_size:
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "upload_file_too_large",
                            "message": f"File too large. Maximum size is {settings.upload_max_megabytes} MB.",
                            "max_megabytes": int(settings.upload_max_megabytes),
                        },
                    )
                await run_in_threadpool(handle.write, chunk)
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    finally:
        try:
            await file.close()
        except Exception:
            pass

    normalized_source_surface = (source_surface or "").strip()[:100] or None

    try:
        novel = accept_novel_upload(
            db,
            title=title,
            author=author,
            file_path=str(file_path),
            owner_id=current_user.id,
            source_bytes=bytes_written,
            requested_language=language,
        )
        db.commit()
        db.refresh(novel)
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    record_event(
        db,
        current_user.id,
        "novel_upload",
        novel_id=novel.id,
        meta={
            "bytes_uploaded": bytes_written,
            "consent_acknowledged": True,
            "consent_version": consent_version,
            "language": novel.language,
            "upload_duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            "source_surface": normalized_source_surface,
        },
    )
    ensure_project_start_event(
        db,
        user_id=current_user.id,
        novel_id=novel.id,
        start_mode="chapter_import",
        meta={
            "entry_action": "novel_upload",
            "source_surface": normalized_source_surface,
        },
    )

    return UploadResponse(
        novel_id=novel.id,
        total_chapters=None,
        message="Upload accepted",
    )


@router.post("/{novel_id}/ingest/retry", response_model=NovelResponse, status_code=202)
def retry_novel_ingest(
    novel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    row = (
        db.query(Novel)
        .options(defer(Novel.window_index))
        .add_columns(novel_support.novel_window_index_presence_column())
        .filter(Novel.id == novel_id)
        .first()
    )
    novel = row[0] if row is not None else None
    novel_support.verify_novel_access(novel, current_user)

    ingest_job = inspect_novel_ingest_job(db, novel_id=novel_id)
    if ingest_job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ingest_job_not_found", "message": "Novel ingest job not found"},
        )
    if ingest_job.status != "failed":
        raise HTTPException(
            status_code=409,
            detail={"code": "ingest_retry_not_allowed", "message": "Novel ingest retry is not allowed"},
        )

    reset_novel_ingest_job_for_retry(db, novel_id=novel_id)

    db.commit()
    db.refresh(novel)

    index_state = inspect_window_index_lifecycle(
        novel,
        db=db,
        has_payload_override=bool(row[1]) if row is not None else None,
    )
    readiness_state = inspect_novel_readiness(
        novel,
        db=db,
        index_state=index_state,
    )
    return novel_support.serialize_novel(
        novel,
        index_state=index_state,
        readiness_state=readiness_state,
    )


@router.delete("/{novel_id}", status_code=204)
def delete_novel(
    novel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    novel_support.verify_novel_access(novel, current_user)

    novel_support.safe_delete_where(
        db,
        table="world_relationships",
        where_sql="novel_id = :novel_id",
        params={"novel_id": novel_id},
    )
    novel_support.safe_delete_where(
        db,
        table="world_entity_attributes",
        where_sql="entity_id IN (SELECT id FROM world_entities WHERE novel_id = :novel_id)",
        params={"novel_id": novel_id},
    )
    novel_support.safe_delete_where(
        db,
        table="world_entities",
        where_sql="novel_id = :novel_id",
        params={"novel_id": novel_id},
    )
    novel_support.safe_delete_where(
        db,
        table="world_systems",
        where_sql="novel_id = :novel_id",
        params={"novel_id": novel_id},
    )
    novel_support.safe_delete_where(
        db,
        table="bootstrap_jobs",
        where_sql="novel_id = :novel_id",
        params={"novel_id": novel_id},
    )
    novel_support.safe_delete_where(
        db,
        table="derived_asset_jobs",
        where_sql="novel_id = :novel_id",
        params={"novel_id": novel_id},
    )

    novel_support.safe_delete_where(
        db,
        table="exploration_chapters",
        where_sql="exploration_id IN (SELECT id FROM explorations WHERE novel_id = :novel_id)",
        params={"novel_id": novel_id},
    )
    novel_support.safe_delete_where(
        db,
        table="explorations",
        where_sql="novel_id = :novel_id",
        params={"novel_id": novel_id},
    )

    legacy_deletes: list[tuple[str, str]] = [
        (
            "character_moments",
            "epoch_id IN (SELECT id FROM character_epochs WHERE arc_id IN (SELECT id FROM character_arcs WHERE novel_id = :novel_id))",
        ),
        ("character_epochs", "arc_id IN (SELECT id FROM character_arcs WHERE novel_id = :novel_id)"),
        ("character_arcs", "novel_id = :novel_id"),
        (
            "plot_beats",
            "thread_id IN (SELECT id FROM plot_threads WHERE arc_id IN (SELECT id FROM plot_arcs WHERE novel_id = :novel_id))",
        ),
        ("plot_threads", "arc_id IN (SELECT id FROM plot_arcs WHERE novel_id = :novel_id)"),
        ("plot_arcs", "novel_id = :novel_id"),
        ("narrative_facts", "novel_id = :novel_id"),
        ("narrative_styles", "novel_id = :novel_id"),
        ("narrative_events", "novel_id = :novel_id"),
    ]
    for table, where_sql in legacy_deletes:
        novel_support.safe_delete_where(
            db,
            table=table,
            where_sql=where_sql,
            params={"novel_id": novel_id},
            allow_missing_column=True,
        )

    file_path = Path(novel.file_path) if novel.file_path else None
    db.delete(novel)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    if file_path is not None:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            novel_support.logger.warning(
                "Failed to delete novel file after DB delete (novel_id=%s, file_path=%s)",
                novel_id,
                str(file_path),
                exc_info=True,
            )

    return Response(status_code=204)
