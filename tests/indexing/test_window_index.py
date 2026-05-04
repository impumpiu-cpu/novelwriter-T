import msgpack

from app.core.indexing.window_index import NovelIndex, WindowRef


def test_window_index_msgpack_round_trip():
    original = NovelIndex(
        entity_windows={
            "云澈": [
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=120, entity_count=5),
                WindowRef(window_id=2, chapter_id=1, start_pos=80, end_pos=200, entity_count=3),
            ],
            "楚月仙": [
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=120, entity_count=5),
            ],
        },
        window_entities={
            1: {"云澈", "楚月仙"},
            2: {"云澈"},
        },
    )

    packed = original.to_msgpack()
    restored = NovelIndex.from_msgpack(packed)

    assert isinstance(packed, bytes)
    assert restored == original


def test_window_index_msgpack_omits_window_entities_from_compact_payload():
    original = NovelIndex(
        entity_windows={
            "云澈": [
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=120, entity_count=5),
            ],
            "楚月仙": [
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=120, entity_count=5),
            ],
        },
        window_entities={
            1: {"云澈", "楚月仙"},
        },
    )

    payload = msgpack.unpackb(original.to_msgpack(), raw=False)

    assert payload["v"] == 2
    assert "w" not in payload
    assert payload["e"]["云澈"][0] == [1, 1, 0, 120, 5]


def test_window_index_from_msgpack_keeps_legacy_payload_compatibility():
    legacy_payload = msgpack.packb(
        {
            "entity_windows": {
                "云澈": [
                    {
                        "window_id": 1,
                        "chapter_id": 1,
                        "start_pos": 0,
                        "end_pos": 120,
                        "entity_count": 5,
                    }
                ],
                "楚月仙": [
                    {
                        "window_id": 1,
                        "chapter_id": 1,
                        "start_pos": 0,
                        "end_pos": 120,
                        "entity_count": 5,
                    }
                ],
            }
        },
        use_bin_type=True,
    )

    restored = NovelIndex.from_msgpack(legacy_payload)

    assert set(restored.window_entities[1]) == {"云澈", "楚月仙"}


def test_find_entity_passages_sorted_by_entity_count():
    index = NovelIndex(
        entity_windows={
            "云澈": [
                WindowRef(window_id=3, chapter_id=1, start_pos=200, end_pos=300, entity_count=2),
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=100, entity_count=5),
                WindowRef(window_id=2, chapter_id=1, start_pos=100, end_pos=200, entity_count=5),
            ]
        },
        window_entities={},
    )

    top = index.find_entity_passages("云澈", limit=2)
    assert [ref.window_id for ref in top] == [1, 2]


def test_find_cooccurrence_intersection():
    index = NovelIndex(
        entity_windows={
            "云澈": [
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=120, entity_count=5),
                WindowRef(window_id=2, chapter_id=1, start_pos=120, end_pos=240, entity_count=3),
                WindowRef(window_id=3, chapter_id=1, start_pos=240, end_pos=360, entity_count=2),
            ],
            "楚月仙": [
                WindowRef(window_id=1, chapter_id=1, start_pos=0, end_pos=120, entity_count=5),
                WindowRef(window_id=3, chapter_id=1, start_pos=240, end_pos=360, entity_count=2),
            ],
        },
        window_entities={},
    )

    co = index.find_cooccurrence("云澈", "楚月仙", limit=10)
    assert [ref.window_id for ref in co] == [1, 3]
