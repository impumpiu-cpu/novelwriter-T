# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.world_support import serialize_worldpack_import_result, translate_worldpack_import_error
from app.core.auth import get_current_user_or_default
from app.core.events import ensure_project_start_event, record_event
from app.core.world.worldpack_import import WorldpackImportError, import_worldpack_payload
from app.database import get_db
from app.models import User
from app.schemas import WorldpackImportResponse, WorldpackV1Payload

router = APIRouter()


@router.post("/worldpack/import", response_model=WorldpackImportResponse)
def import_worldpack_v1(
    novel_id: int,
    body: WorldpackV1Payload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    try:
        result = import_worldpack_payload(novel_id=novel_id, body=body, db=db)
    except WorldpackImportError as exc:
        raise translate_worldpack_import_error(exc) from exc
    ensure_project_start_event(
        db,
        user_id=current_user.id,
        novel_id=novel_id,
        start_mode="setting_import",
        meta={"entry_action": "worldpack_import"},
    )
    record_event(
        db,
        current_user.id,
        "worldpack_import",
        novel_id=novel_id,
        meta={
            "pack_id": result.pack_id,
            "warnings_count": len(result.warnings),
            "entities_created": result.counts.entities_created,
            "relationships_created": result.counts.relationships_created,
            "systems_created": result.counts.systems_created,
        },
    )
    return serialize_worldpack_import_result(result)


__all__ = ["import_worldpack_v1", "router"]
