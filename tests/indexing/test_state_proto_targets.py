from __future__ import annotations

from app.core.indexing.state_proto import TARGET_KIND_ARTIFACT, TARGET_KIND_ENTITY
from app.core.indexing.state_proto_targets import (
    build_state_proto_target_specs_from_world_entities,
    resolve_world_entity_target_kind,
)
from app.models import WorldEntity


def test_resolve_world_entity_target_kind_detects_artifact_like_types():
    assert resolve_world_entity_target_kind("Artifact") == TARGET_KIND_ARTIFACT
    assert resolve_world_entity_target_kind("武器") == TARGET_KIND_ARTIFACT
    assert resolve_world_entity_target_kind("Character") == TARGET_KIND_ENTITY


def test_build_state_proto_target_specs_from_world_entities_preserves_aliases():
    entity = WorldEntity(
        id=7,
        novel_id=1,
        name="玄铁令",
        entity_type="Artifact",
        aliases=["玄令", "玄铁令", "  玄令  "],
    )

    specs = build_state_proto_target_specs_from_world_entities([entity])

    assert len(specs) == 1
    assert specs[0].id == "entity:7"
    assert specs[0].canonical_name == "玄铁令"
    assert specs[0].kind == TARGET_KIND_ARTIFACT
    assert specs[0].aliases == ("玄令",)
