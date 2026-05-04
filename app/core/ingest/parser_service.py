from __future__ import annotations

from app.core.parser import parse_novel_file_streaming, probe_novel_file
from app.language import normalize_language_code

from .contracts import ParsedNovelIngest


def resolve_requested_language(language: str | None) -> str | None:
    return normalize_language_code(language, default=None)


def parse_source_file(
    file_path: str,
    *,
    requested_language: str | None,
) -> ParsedNovelIngest:
    detected_encoding, source_chars, resolved_language = probe_novel_file(
        file_path,
        requested_language=requested_language,
    )
    chapters = parse_novel_file_streaming(
        file_path,
        encoding=detected_encoding,
        language=resolved_language,
    )
    return ParsedNovelIngest(
        source_chars=source_chars,
        resolved_language=resolved_language,
        chapters=chapters,
    )
