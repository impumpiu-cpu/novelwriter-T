# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

"""Application orchestration for text-to-world generation."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.ai_client import LLMUnavailableError, StructuredOutputParseError
from app.core.events import ensure_project_start_event, record_event
from app.core.world.crud import load_novel
from app.core.world.gen import generate_world_drafts
from app.core.world.generation_runs import (
    build_world_generation_request_hash,
    claim_world_generation_run,
    complete_world_generation_run,
    fail_world_generation_run,
)
from app.core.world.use_case_errors import WorldUseCaseError, detail_error_from_http_exception
from app.core.auth import ensure_ai_available, refund_quota, reserve_quota
from app.core.llm_semaphore import acquire_llm_slot, release_llm_slot
from app.models import User
from app.schemas import WorldGenerateResponse

logger = logging.getLogger(__name__)
_world_generate_locks: dict[int, asyncio.Lock] = {}
_world_generate_locks_guard = asyncio.Lock()


def _world_generation_error_from_http_exception(exc: HTTPException) -> tuple[str, str]:
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code") or "world_generate_failed")
        message = str(exc.detail.get("message") or code)
        return code[:64], message
    return "world_generate_failed", str(exc.detail)


def _resolve_world_generation_billing_source(llm_config: dict | None) -> str | None:
    if not isinstance(llm_config, dict):
        return None
    hint = llm_config.get("billing_source_hint")
    if not isinstance(hint, str):
        return None
    normalized = hint.strip().lower()
    return normalized or None


async def generate_world_from_text(
    novel_id: int,
    *,
    text: str,
    db: Session,
    current_user: User,
    llm_config: dict | None,
    request_id: str | None = None,
    generate_world_drafts_fn: Callable[..., Awaitable[WorldGenerateResponse]] | None = None,
    acquire_llm_slot_fn: Callable[[], Awaitable[None]] | None = None,
    release_llm_slot_fn: Callable[[], None] | None = None,
    reserve_quota_fn: Callable[[Session, int, int], None] | None = None,
    refund_quota_fn: Callable[[Session, int, int], None] | None = None,
    record_event_fn: Callable[..., None] | None = None,
) -> WorldGenerateResponse:
    generation_runner = generate_world_drafts_fn or generate_world_drafts
    acquire_slot = acquire_llm_slot_fn or acquire_llm_slot
    release_slot = release_llm_slot_fn or release_llm_slot
    reserve_quota_write = reserve_quota_fn or reserve_quota
    refund_quota_write = refund_quota_fn or refund_quota
    record_generate_event = record_event_fn or record_event

    load_novel(novel_id, db)
    claim_token = secrets.token_hex(16)
    run_claim = claim_world_generation_run(
        db,
        user_id=current_user.id,
        novel_id=novel_id,
        request_hash=build_world_generation_request_hash(text=text),
        claim_token=claim_token,
    )
    if not run_claim.owner:
        raise WorldUseCaseError(
            code="world_generate_duplicate_request",
            message="World generation already running for this novel",
            status_code=409,
        )

    try:
        ensure_ai_available(
            db,
            billing_source=_resolve_world_generation_billing_source(llm_config),
        )
    except HTTPException as exc:
        error_code, error_message = _world_generation_error_from_http_exception(exc)
        fail_world_generation_run(
            db,
            run_id=run_claim.run_id,
            claim_token=claim_token,
            error_code=error_code,
            error_message=error_message,
        )
        raise detail_error_from_http_exception(exc) from exc

    lock = await _get_world_generate_lock(novel_id)
    async with lock:
        extra = {
            "request_id": request_id,
            "novel_id": novel_id,
            "user_id": current_user.id,
        }

        slot_acquired = False
        try:
            await acquire_slot()
            slot_acquired = True
        except HTTPException as exc:
            error_code, error_message = _world_generation_error_from_http_exception(exc)
            fail_world_generation_run(
                db,
                run_id=run_claim.run_id,
                claim_token=claim_token,
                error_code=error_code,
                error_message=error_message,
            )
            raise detail_error_from_http_exception(exc) from exc

        reserved = False
        try:
            try:
                reserve_quota_write(db, current_user.id, 1)
                reserved = True
                result = await generation_runner(
                    db=db,
                    novel_id=novel_id,
                    text=text,
                    llm_config=llm_config,
                    user_id=current_user.id,
                )
            except HTTPException as exc:
                if reserved:
                    refund_quota_write(db, current_user.id, 1)
                error_code, error_message = _world_generation_error_from_http_exception(exc)
                fail_world_generation_run(
                    db,
                    run_id=run_claim.run_id,
                    claim_token=claim_token,
                    error_code=error_code,
                    error_message=error_message,
                )
                raise detail_error_from_http_exception(exc) from exc
            except StructuredOutputParseError as exc:
                if reserved:
                    refund_quota_write(db, current_user.id, 1)
                logger.warning("world.generate invalid LLM output", exc_info=True, extra=extra)
                fail_world_generation_run(
                    db,
                    run_id=run_claim.run_id,
                    claim_token=claim_token,
                    error_code="world_generate_llm_schema_invalid",
                    error_message="LLM schema invalid",
                )
                raise WorldUseCaseError(
                    code="world_generate_llm_schema_invalid",
                    message="LLM schema invalid",
                    status_code=502,
                ) from exc
            except LLMUnavailableError as exc:
                if reserved:
                    refund_quota_write(db, current_user.id, 1)
                logger.warning("world.generate LLM unavailable", exc_info=True, extra=extra)
                fail_world_generation_run(
                    db,
                    run_id=run_claim.run_id,
                    claim_token=claim_token,
                    error_code="world_generate_llm_unavailable",
                    error_message="LLM unavailable",
                )
                raise WorldUseCaseError(
                    code="world_generate_llm_unavailable",
                    message="LLM unavailable",
                    status_code=503,
                ) from exc
            except IntegrityError as exc:
                if reserved:
                    refund_quota_write(db, current_user.id, 1)
                fail_world_generation_run(
                    db,
                    run_id=run_claim.run_id,
                    claim_token=claim_token,
                    error_code="world_generate_conflict",
                    error_message="World generation conflict",
                )
                raise WorldUseCaseError(
                    code="world_generate_conflict",
                    message="World generation conflict",
                    status_code=409,
                ) from exc
            except Exception as exc:
                if reserved:
                    refund_quota_write(db, current_user.id, 1)
                logger.exception("world.generate failed", extra=extra)
                fail_world_generation_run(
                    db,
                    run_id=run_claim.run_id,
                    claim_token=claim_token,
                    error_code="world_generate_failed",
                    error_message="World generation failed",
                )
                raise WorldUseCaseError(
                    code="world_generate_failed",
                    message="World generation failed",
                    status_code=500,
                ) from exc
        finally:
            if slot_acquired:
                release_slot()

        complete_world_generation_run(
            db,
            run_id=run_claim.run_id,
            claim_token=claim_token,
            response_payload=result.model_dump(mode="json"),
        )
        ensure_project_start_event(
            db,
            user_id=current_user.id,
            novel_id=novel_id,
            start_mode="setting_import",
            meta={"entry_action": "world_generate"},
        )
        record_generate_event(
            db,
            current_user.id,
            "world_generate",
            novel_id=novel_id,
            meta={
                "entities_created": result.entities_created,
                "relationships_created": result.relationships_created,
                "systems_created": result.systems_created,
                "warnings_count": len(result.warnings),
            },
        )
        return result


async def _get_world_generate_lock(novel_id: int) -> asyncio.Lock:
    async with _world_generate_locks_guard:
        lock = _world_generate_locks.get(novel_id)
        if lock is None:
            lock = asyncio.Lock()
            _world_generate_locks[novel_id] = lock
        return lock
