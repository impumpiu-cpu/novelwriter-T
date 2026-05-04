# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared copilot scope types, limits, and text helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.copilot.messages import CopilotTextKey, get_copilot_text
from app.core.indexing import WindowIndexLifecycleSnapshot
from app.language_policy import get_language_policy
from app.models import (
    WorldEntity,
    WorldEntityAttribute,
    WorldRelationship,
    WorldSystem,
    Novel,
)

CopilotRuntimeProfile = Literal[
    "focused_research", "draft_governance", "broad_exploration"
]
CopilotFocusVariant = Literal["entity", "relationship", "draft", "whole_book"]

MAX_EVIDENCE_ITEMS = 15
MAX_SCOPE_ENTITIES = 80
MAX_SCOPE_RELATIONSHIPS = 60
MAX_SCOPE_SYSTEMS = 30
MAX_CHAPTER_EXCERPT_CHARS = 2000


@dataclass(frozen=True)
class EntityLookupRef:
    entity_id: int
    name: str
    status: str


@dataclass(frozen=True)
class SystemLookupRef:
    system_id: int
    name: str
    status: str


@dataclass
class ScopeSnapshot:
    """World-model state loaded by the backend for a copilot scope."""

    novel: Novel
    novel_language: str
    entities: list[WorldEntity]
    entities_by_id: dict[int, WorldEntity]
    relationships: list[WorldRelationship]
    systems: list[WorldSystem]
    attributes_by_entity: dict[int, list[WorldEntityAttribute]]
    draft_entities: list[WorldEntity]
    draft_relationships: list[WorldRelationship]
    draft_systems: list[WorldSystem]
    profile: str = "broad_exploration"
    focus_variant: str = "whole_book"
    focus_entity_id: int | None = None
    window_index_state: WindowIndexLifecycleSnapshot | None = None
    novel_entity_refs_by_name_key: dict[str, tuple[EntityLookupRef, ...]] = field(
        default_factory=dict
    )
    novel_system_refs_by_name_key: dict[str, tuple[SystemLookupRef, ...]] = field(
        default_factory=dict
    )


@dataclass
class EvidenceItem:
    """A backend-sourced, verifiable evidence item."""

    evidence_id: str
    source_type: str
    source_ref: dict[str, Any]
    title: str
    excerpt: str
    why_relevant: str
    pack_id: str | None = None
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    anchor_terms: list[str] = field(default_factory=list)
    support_count: int | None = None
    preview_excerpt: str | None = None
    expanded: bool = False


def scope_text(
    interaction_locale: str,
    text_key: CopilotTextKey,
    **params: object,
) -> str:
    return get_copilot_text(text_key, locale=interaction_locale, **params)


def append_scope_labeled_line(
    text: str,
    *,
    interaction_locale: str,
    label_key: CopilotTextKey,
    value: str,
) -> str:
    label = scope_text(interaction_locale, label_key)
    return f"{text}\n{label}: {value}"


def normalize_lookup_key(value: str | None, *, language: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return get_language_policy(language, sample_text=text).normalize_for_matching(text)
