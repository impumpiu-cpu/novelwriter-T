from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.parser import ParsedChapter

IngestSizeTier = Literal["normal", "large", "xlarge", "reject"]
AutoIndexPlan = Literal["immediate", "deferred", "skip_auto"]
BootstrapPlan = Literal["immediate", "defer_until_index", "manual_only"]
ReadinessMode = Literal["full_target", "degraded_target"]


@dataclass(frozen=True, slots=True)
class IngestPolicyInput:
    source_bytes: int
    source_chars: int
    chapter_count: int


@dataclass(frozen=True, slots=True)
class IngestPolicyDecision:
    size_tier: IngestSizeTier
    auto_index_plan: AutoIndexPlan
    bootstrap_plan: BootstrapPlan
    readiness_mode: ReadinessMode


@dataclass(frozen=True, slots=True)
class ParsedNovelIngest:
    source_chars: int
    resolved_language: str
    chapters: list[ParsedChapter]
