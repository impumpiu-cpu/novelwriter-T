from app.core.bootstrap_persistence import _normalize_aliases


def test_normalize_aliases_preserves_zh_surface_variants():
    assert _normalize_aliases(["凤雪児"], "凤雪儿") == ["凤雪児"]


def test_normalize_aliases_still_dedupes_non_zh_equivalent_aliases():
    assert _normalize_aliases(["john smith", "John Smith"], "John Smith") == []
