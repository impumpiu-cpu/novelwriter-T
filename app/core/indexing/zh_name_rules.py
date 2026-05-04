from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

_DATA_DIR = Path(__file__).resolve().parent / "data"
_CJK_NAME_TOKEN_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+$")


def _read_data_file(filename: str) -> str:
    return (_DATA_DIR / filename).read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def get_zh_single_surnames() -> frozenset[str]:
    return frozenset(_read_data_file("zh_single_surnames.txt"))


@lru_cache(maxsize=1)
def get_zh_compound_surnames() -> frozenset[str]:
    return frozenset(
        line.strip()
        for line in _read_data_file("zh_compound_surnames.txt").splitlines()
        if line.strip()
    )


@lru_cache(maxsize=1)
def get_zh_name_trailing_noise_chars() -> frozenset[str]:
    return frozenset(_read_data_file("zh_name_trailing_noise_chars.txt"))


@lru_cache(maxsize=1)
def get_zh_translit_chars() -> frozenset[str]:
    return frozenset(
        ch for ch in _read_data_file("zh_translit_chars.txt") if not ch.isspace()
    )


@lru_cache(maxsize=1)
def get_zh_name_suffix_titles() -> frozenset[str]:
    return frozenset(
        line.strip()
        for line in _read_data_file("zh_name_suffix_titles.txt").splitlines()
        if line.strip()
    )


def is_cjk_name_token(token: str) -> bool:
    return bool(token) and bool(_CJK_NAME_TOKEN_RE.fullmatch(token))


def looks_like_zh_translit_fragment(token: str) -> bool:
    return bool(token) and is_cjk_name_token(token) and all(
        char in get_zh_translit_chars() for char in token
    )


def is_zh_name_suffix_title(token: str) -> bool:
    return bool(token) and token in get_zh_name_suffix_titles()


def merge_split_zh_name_tokens(left: str, right: str) -> str | None:
    if not is_cjk_name_token(left) or not is_cjk_name_token(right):
        return None

    left_len = len(left)
    right_len = len(right)
    trailing_noise_chars = get_zh_name_trailing_noise_chars()
    compound_surnames = get_zh_compound_surnames()
    single_surnames = get_zh_single_surnames()

    if right_len == 1 and right in trailing_noise_chars:
        return None

    if left_len == 2 and left in compound_surnames and right_len in {1, 2}:
        return left + right
    if left_len == 3 and left[:2] in compound_surnames and right_len == 1:
        return left + right
    if left_len == 1 and left in single_surnames and right_len == 2:
        return left + right
    if left_len == 2 and left[:1] in single_surnames and right_len == 1:
        return left + right
    return None


def looks_like_zh_person_name(token: str) -> bool:
    if not is_cjk_name_token(token):
        return False

    token_len = len(token)
    compound_surnames = get_zh_compound_surnames()
    single_surnames = get_zh_single_surnames()

    if token_len == 2:
        return token[:1] in single_surnames
    if token_len == 3:
        return token[:1] in single_surnames or token[:2] in compound_surnames
    if token_len == 4:
        return token[:2] in compound_surnames
    return False


def strip_zh_person_name_trailing_noise(token: str) -> str | None:
    if not is_cjk_name_token(token) or len(token) < 3:
        return None

    canonical = token[:-1]
    if token[-1] not in get_zh_name_trailing_noise_chars():
        return None
    if not looks_like_zh_person_name(canonical):
        return None
    return canonical


__all__ = [
    "get_zh_compound_surnames",
    "get_zh_name_trailing_noise_chars",
    "get_zh_name_suffix_titles",
    "get_zh_single_surnames",
    "get_zh_translit_chars",
    "is_zh_name_suffix_title",
    "is_cjk_name_token",
    "looks_like_zh_person_name",
    "looks_like_zh_translit_fragment",
    "merge_split_zh_name_tokens",
    "strip_zh_person_name_trailing_noise",
]
