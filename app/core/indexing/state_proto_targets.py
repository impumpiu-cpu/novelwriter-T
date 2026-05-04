from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models import WorldEntity

from .state_proto_model import TARGET_KIND_ARTIFACT, TARGET_KIND_ENTITY, TargetSpec


_ARTIFACT_TYPE_MARKERS = {
    "artifact",
    "artifacts",
    "item",
    "items",
    "object",
    "objects",
    "relic",
    "relics",
    "weapon",
    "weapons",
    "tool",
    "tools",
    "treasure",
    "物品",
    "法宝",
    "器物",
    "道具",
    "武器",
    "宝物",
}


def resolve_world_entity_target_kind(entity_type: str | None) -> str:
    normalized = (entity_type or "").strip().lower()
    if normalized in _ARTIFACT_TYPE_MARKERS:
        return TARGET_KIND_ARTIFACT
    if any(marker in normalized for marker in _ARTIFACT_TYPE_MARKERS):
        return TARGET_KIND_ARTIFACT
    return TARGET_KIND_ENTITY


def build_state_proto_target_specs_from_world_entities(
    entities: Iterable[WorldEntity],
) -> tuple[TargetSpec, ...]:
    specs: list[TargetSpec] = []
    for entity in entities:
        alias_values: list[str] = []
        seen_aliases: set[str] = set()
        for raw_alias in entity.aliases or []:
            if not isinstance(raw_alias, str):
                continue
            alias = raw_alias.strip()
            if not alias or alias == (entity.name or "").strip() or alias in seen_aliases:
                continue
            seen_aliases.add(alias)
            alias_values.append(alias)
        specs.append(
            TargetSpec(
                id=f"entity:{int(entity.id)}",
                canonical_name=(entity.name or "").strip(),
                kind=resolve_world_entity_target_kind(getattr(entity, "entity_type", None)),
                aliases=tuple(alias_values),
            )
        )
    return tuple(spec for spec in specs if spec.canonical_name)


def load_state_proto_target_specs(db: Session, novel_id: int) -> tuple[TargetSpec, ...]:
    entities = (
        db.query(WorldEntity)
        .filter(WorldEntity.novel_id == novel_id)
        .order_by(WorldEntity.status.asc(), WorldEntity.id.asc())
        .all()
    )
    return build_state_proto_target_specs_from_world_entities(entities)
