# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_or_default
from app.core.world.application import (
    batch_confirm_entities as confirm_entity_drafts,
    batch_reject_entities as reject_entity_drafts,
    create_attribute as create_attribute_use_case,
    create_entity as create_entity_use_case,
    delete_attribute as delete_attribute_use_case,
    delete_entity as delete_entity_use_case,
    reorder_attributes as reorder_attribute_values,
    update_attribute as update_attribute_use_case,
    update_entity as update_entity_use_case,
)
from app.database import get_db
from app.models import User, WorldEntity
from app.schemas import (
    AttributeReorderRequest,
    BatchConfirmRequest,
    BatchConfirmResponse,
    BatchRejectRequest,
    BatchRejectResponse,
    WorldAttributeCreate,
    WorldAttributeUpdate,
    WorldEntityAttributeResponse,
    WorldEntityCreate,
    WorldEntityDetailResponse,
    WorldEntityResponse,
    WorldEntityUpdate,
    WorldOrigin,
)
from app.api.world_support import (
    WorldModelRowStatus,
    apply_exact_filters,
    apply_ilike_search,
    get_entity as load_world_entity,
    get_novel,
    run_user_batch_operation,
    run_user_payload_operation,
    run_world_operation,
)

router = APIRouter()


@router.get("/entities", response_model=List[WorldEntityResponse])
def list_entities(
    novel_id: int,
    q: Optional[str] = None,
    entity_type: Optional[str] = None,
    origin: Optional[WorldOrigin] = None,
    worldpack_pack_id: Optional[str] = None,
    worldpack_key: Optional[str] = None,
    status: Optional[WorldModelRowStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    get_novel(novel_id, db)
    query = db.query(WorldEntity).filter(WorldEntity.novel_id == novel_id)
    query = apply_ilike_search(query, q, WorldEntity.name, WorldEntity.description)
    query = apply_exact_filters(
        query,
        (WorldEntity.entity_type, entity_type),
        (WorldEntity.origin, origin),
        (WorldEntity.worldpack_pack_id, worldpack_pack_id),
        (WorldEntity.worldpack_key, worldpack_key),
        (WorldEntity.status, status),
    )
    return query.order_by(WorldEntity.id.asc()).all()


@router.post("/entities", response_model=WorldEntityResponse, status_code=201)
def create_entity(
    novel_id: int,
    body: WorldEntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    return run_user_payload_operation(
        create_entity_use_case,
        novel_id,
        body=body,
        current_user_id=current_user.id,
        db=db,
    )


@router.get("/entities/{entity_id}", response_model=WorldEntityDetailResponse)
def get_entity_route(
    novel_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    get_novel(novel_id, db)
    return load_world_entity(novel_id, entity_id, db)


@router.put("/entities/{entity_id}", response_model=WorldEntityResponse)
def update_entity(
    novel_id: int,
    entity_id: int,
    body: WorldEntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    return run_user_payload_operation(
        update_entity_use_case,
        novel_id,
        entity_id,
        body=body,
        current_user_id=current_user.id,
        db=db,
        exclude_none=True,
    )


@router.delete("/entities/{entity_id}")
def delete_entity(
    novel_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    run_world_operation(delete_entity_use_case, novel_id, entity_id, db=db)
    return {"message": "Entity deleted"}


@router.post("/entities/confirm", response_model=BatchConfirmResponse)
def batch_confirm_entities(
    novel_id: int,
    body: BatchConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    count = run_user_batch_operation(
        confirm_entity_drafts,
        novel_id,
        body.ids,
        current_user_id=current_user.id,
        db=db,
    )
    return BatchConfirmResponse(confirmed=count)


@router.post("/entities/reject", response_model=BatchRejectResponse)
def batch_reject_entities(
    novel_id: int,
    body: BatchRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    count = run_user_batch_operation(
        reject_entity_drafts,
        novel_id,
        body.ids,
        current_user_id=current_user.id,
        db=db,
    )
    return BatchRejectResponse(rejected=count)


@router.post("/entities/{entity_id}/attributes", response_model=WorldEntityAttributeResponse, status_code=201)
def add_attribute(
    novel_id: int,
    entity_id: int,
    body: WorldAttributeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    return run_world_operation(create_attribute_use_case, novel_id, entity_id, body.model_dump(), db=db)


@router.put("/entities/{entity_id}/attributes/{attribute_id}", response_model=WorldEntityAttributeResponse)
def update_attribute(
    novel_id: int,
    entity_id: int,
    attribute_id: int,
    body: WorldAttributeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    return run_world_operation(
        update_attribute_use_case,
        novel_id,
        entity_id,
        attribute_id,
        body.model_dump(exclude_none=True),
        db=db,
    )


@router.delete("/entities/{entity_id}/attributes/{attribute_id}")
def delete_attribute(
    novel_id: int,
    entity_id: int,
    attribute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    run_world_operation(delete_attribute_use_case, novel_id, entity_id, attribute_id, db=db)
    return {"message": "Attribute deleted"}


@router.patch("/entities/{entity_id}/attributes/reorder")
def reorder_attributes(
    novel_id: int,
    entity_id: int,
    body: AttributeReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_default),
):
    _ = current_user
    run_world_operation(reorder_attribute_values, novel_id, entity_id, body.order, db=db)
    return {"message": "Reordered"}


get_entity = get_entity_route


__all__ = [
    "add_attribute",
    "batch_confirm_entities",
    "batch_reject_entities",
    "create_entity",
    "delete_attribute",
    "delete_entity",
    "get_entity",
    "list_entities",
    "reorder_attributes",
    "router",
    "update_attribute",
    "update_entity",
]
