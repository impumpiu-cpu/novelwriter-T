from __future__ import annotations

from app.core.indexing import builder


def test_jieba_tokenizer_prefers_rust_extension(monkeypatch):
    class FakeRustTokenizer:
        @staticmethod
        def tokenize_zh_text(text: str) -> list[str]:
            assert text == "云澈 看向 远方"
            return ["云澈", "", "远方"]

    monkeypatch.setattr(builder, "_novwr_state_proto", FakeRustTokenizer())

    assert builder.JiebaTokenizer().tokenize("云澈 看向 远方") == ["云澈", "远方"]


def test_jieba_tokenizer_falls_back_to_character_ngrams_when_rust_helper_missing(monkeypatch):
    class MissingHelperModule:
        pass

    monkeypatch.setattr(builder, "_novwr_state_proto", MissingHelperModule())

    assert builder.JiebaTokenizer().tokenize("云澈看向远方") == [
        "云澈",
        "澈看",
        "看向",
        "向远",
        "远方",
    ]


def test_jieba_tokenizer_falls_back_to_character_ngrams_when_rust_extension_unavailable(monkeypatch):
    monkeypatch.setattr(builder, "_novwr_state_proto", None)

    assert builder.JiebaTokenizer().tokenize("云澈看向远方") == [
        "云澈",
        "澈看",
        "看向",
        "向远",
        "远方",
    ]
