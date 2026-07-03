"""Валидация комплектных worldpack-шаблонов из data/worldpacks."""

import json
from pathlib import Path

import pytest

from app.schemas import WorldpackV1Payload

WORLDPACKS_DIR = Path(__file__).parent.parent.parent / "data" / "worldpacks"


@pytest.mark.parametrize(
    "worldpack_path",
    sorted(WORLDPACKS_DIR.glob("*.json")),
    ids=lambda path: path.name,
)
def test_bundled_worldpack_matches_v1_schema(worldpack_path):
    payload = WorldpackV1Payload.model_validate(
        json.loads(worldpack_path.read_text(encoding="utf-8"))
    )
    assert payload.schema_version == "worldpack.v1"
    assert payload.entities, f"{worldpack_path.name} must ship at least one entity"


def test_technical_writer_starter_covers_technical_entity_types():
    payload = WorldpackV1Payload.model_validate(
        json.loads(
            (WORLDPACKS_DIR / "technical-writer-starter.json").read_text(encoding="utf-8")
        )
    )
    entity_types = {entity.entity_type for entity in payload.entities}
    assert {"Оборудование", "Вещество", "Датчик", "Документ", "Требование"} <= entity_types
