from app.core.generator import _trim_to_target_chars
from app.language_policy import (
    detect_language_from_text,
    detect_language_from_texts,
    get_language_policy,
)


def test_detect_language_from_text_supports_cjk_families():
    assert detect_language_from_text("Alice and Bob walked home.") == "en"
    assert detect_language_from_text("云澈看向远方。") == "zh"
    assert detect_language_from_text("勇者は城へ向かった。") == "ja"
    assert detect_language_from_text("민수는 집으로 돌아갔다.") == "ko"


def test_detect_language_from_text_ignores_sparse_kana_noise_in_chinese_text():
    noisy_chinese = (
        "云澈看向前方，周围的人都屏住了呼吸。"
        "他抬起手时，所有人都感到心口发紧。"
        "这段正文里混进了少量乱码假名ぃアご。"
    )

    assert detect_language_from_text(noisy_chinese) == "zh"


def test_detect_language_from_texts_ignores_sparse_kana_noise_in_chinese_text():
    texts = (
        "云澈看向前方，周围的人都屏住了呼吸。",
        "他抬起手时，所有人都感到心口发紧。",
        "这段正文里混进了少量乱码假名ぃアご。",
    )

    assert detect_language_from_texts(texts) == "zh"


def test_zh_policy_normalizes_variant_characters_for_matching():
    policy = get_language_policy("zh")

    assert policy.normalize_for_matching("凤雪児") == policy.normalize_for_matching("凤雪儿")
    assert policy.normalize_token("凤雪児。") == "凤雪儿"


def test_ja_policy_does_not_rewrite_variant_characters_into_chinese_forms():
    policy = get_language_policy("ja")

    assert policy.normalize_for_matching("雪児") == "雪児"
    assert policy.normalize_token("雪児。") == "雪児"


def test_english_policy_trims_at_period_boundary():
    trimmed = get_language_policy("en").trim_to_sentence_boundary(
        "Alpha beta. Gamma delta. Omega",
        17,
    )

    assert trimmed == "Alpha beta."


def test_english_policy_treats_apostrophes_as_word_boundaries():
    policy = get_language_policy("en")
    straight = "Alice's lantern dimmed."
    curly = "Alice’s lantern dimmed."

    straight_start = straight.index("Alice")
    curly_start = curly.index("Alice")

    assert policy.match_has_word_boundaries(straight, straight_start, straight_start + len("Alice"))
    assert policy.match_has_word_boundaries(curly, curly_start, curly_start + len("Alice"))


def test_generator_trim_uses_language_policy_for_english():
    trimmed = _trim_to_target_chars(
        "Alpha beta. Gamma delta. Omega",
        17,
        language="en",
    )

    assert trimmed == "Alpha beta."
