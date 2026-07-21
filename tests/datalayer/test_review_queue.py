from datalayer.review_queue import (
    IGNORE, NormalizedField, ReviewQueue, load_overrides, map_or_queue, normalize,
    render_coverage_line, save_overrides,
)


def _upper_keyword(raw: str) -> str | None:
    return raw.upper() if raw.isalpha() else None


def test_map_or_queue_override_canonical_short_circuits_keyword():
    q = ReviewQueue()
    canon = map_or_queue("noir", field="color", brand="b", source="title",
                         keyword_fn=lambda r: None, overrides={"noir": "Black"}, queue=q)
    assert canon == "Black"
    assert q.entries() == []  # override 있으면 큐에 안 올라감(재질문 X)


def test_map_or_queue_override_ignore_returns_none_and_skips_queue():
    q = ReviewQueue()
    canon = map_or_queue("SS26", field="item", brand="b", source="product_type",
                         keyword_fn=lambda r: None, overrides={"ss26": IGNORE}, queue=q)
    assert canon is None
    assert q.entries() == []  # IGNORE도 재질문 X


def test_map_or_queue_keyword_match_no_queue():
    q = ReviewQueue()
    canon = map_or_queue("sweater", field="item", brand="b", source="title",
                         keyword_fn=_upper_keyword, overrides={}, queue=q)
    assert canon == "SWEATER"
    assert q.entries() == []


def test_map_or_queue_unmatched_queues_and_returns_none():
    # SS26/70%Wool 류: 진짜 비값 → None + 큐 (AC fixture)
    q = ReviewQueue()
    for raw in ("SS26", "70%Wool"):
        canon = map_or_queue(raw, field="item", brand="cashmereinlove", source="product_type",
                             keyword_fn=lambda r: None, overrides={}, queue=q)
        assert canon is None
    entries = {e.raw_value: e for e in q.entries()}
    assert set(entries) == {"SS26", "70%Wool"}
    assert entries["SS26"].field == "item" and entries["SS26"].brand == "cashmereinlove"
    assert entries["SS26"].count == 1


def test_map_or_queue_dedups_by_distinct_string_and_counts_products():
    q = ReviewQueue()
    for pid in ("p1", "p1", "p2"):  # p1이 두 번(예: 재실행) → distinct는 상품 단위로 중복제거
        map_or_queue("noir", field="color", brand="b", source="title",
                     keyword_fn=lambda r: None, overrides={}, queue=q, product_id=pid)
    e = q.get("color", "b", "noir")
    assert e.count == 3        # 호출 횟수
    assert e.distinct == 2     # 상품 중복제거


def test_map_or_queue_llm_triage_only_above_threshold():
    calls = []
    q = ReviewQueue()

    def llm(raw):
        calls.append(raw)
        return "제안"

    for i in range(2):  # count=1,2 < threshold(3)
        map_or_queue("eclipse", field="color", brand="b", source="title",
                     keyword_fn=lambda r: None, overrides={}, queue=q,
                     product_id=f"p{i}", threshold=3, llm_fn=llm)
    assert calls == [], "임계 미만이면 LLM 미호출"
    map_or_queue("eclipse", field="color", brand="b", source="title",
                keyword_fn=lambda r: None, overrides={}, queue=q,
                product_id="p3", threshold=3, llm_fn=llm)
    assert calls == ["eclipse"], "임계 도달 시 1회 호출"
    entry = q.get("color", "b", "eclipse")
    assert entry.llm_suggestion == "제안"
    # 이미 제안이 있으면 재호출 안 함
    map_or_queue("eclipse", field="color", brand="b", source="title",
                keyword_fn=lambda r: None, overrides={}, queue=q,
                product_id="p4", threshold=3, llm_fn=llm)
    assert calls == ["eclipse"]


def test_map_or_queue_none_or_blank_raw_ignored():
    q = ReviewQueue()
    assert map_or_queue(None, field="item", brand="b", source="title",
                        keyword_fn=lambda r: None, overrides={}, queue=q) is None
    assert map_or_queue("   ", field="item", brand="b", source="title",
                        keyword_fn=lambda r: None, overrides={}, queue=q) is None
    assert q.entries() == []


def test_queue_save_load_roundtrip(tmp_path):
    q = ReviewQueue()
    map_or_queue("SS26", field="item", brand="b", source="product_type",
                 keyword_fn=lambda r: None, overrides={}, queue=q, product_id="p1")
    path = tmp_path / "item_review_queue.json"
    q.save(path)
    loaded = ReviewQueue.load(path)
    e = loaded.get("item", "b", "SS26")
    assert e is not None and e.count == 1 and e.distinct == 1


def test_overrides_save_load_roundtrip_case_insensitive(tmp_path):
    path = tmp_path / "item_overrides.json"
    save_overrides(path, {"Noir": "Black", "SS26": IGNORE})
    loaded = load_overrides(path)
    assert loaded == {"noir": "Black", "ss26": IGNORE}


def test_load_overrides_missing_file_returns_empty():
    assert load_overrides("/nonexistent/path/overrides.json") == {}


def _upper_or_none(raw: str) -> str | None:
    return raw.upper() if raw.isalpha() else None


def test_normalize_single_value_returns_first_canon_across_sources():
    # 아이템류: product_type 미매칭 → title에서 매칭, 첫 canon 반환
    ITEM = NormalizedField(
        name="item", keyword_fn=_upper_or_none, multi_value=False,
        extract=lambda p: [(p.get("product_type"), "product_type"), (p.get("title"), "title")],
    )
    q = ReviewQueue()
    out = normalize(ITEM, {"product_type": "SS26", "title": "sweater"},
                    brand="b", queue=q, overrides={})
    assert out == "SWEATER"
    # 미매칭 source(SS26)는 큐에 남음
    assert q.get("item", "b", "SS26") is not None


def test_normalize_multi_value_collects_all_canons_dedup():
    # 색/실루엣류: 한 상품서 여러 raw 후보 → 매칭 canon 전부 수집(순서유지·중복제거)
    SIL = NormalizedField(
        name="silhouette", keyword_fn=_upper_or_none, multi_value=True,
        extract=lambda p: [(w, "body") for w in p["words"]],
    )
    q = ReviewQueue()
    out = normalize(SIL, {"words": ["relaxed", "oversized", "relaxed", "70%wool"]},
                    brand="b", queue=q, overrides={})
    assert out == ["RELAXED", "OVERSIZED"]           # dedup + 순서유지
    assert q.get("silhouette", "b", "70%wool") is not None  # 미매칭은 큐


def test_normalize_multi_value_empty_when_no_match():
    SIL = NormalizedField(name="silhouette", keyword_fn=lambda r: None, multi_value=True,
                          extract=lambda p: [("xyz", "body")])
    assert normalize(SIL, {}, brand="b", queue=ReviewQueue(), overrides={}) == []


def test_render_coverage_line_three_tiers():
    assert "🔴" in render_coverage_line(20, 100)   # ==20% → 상단 강조
    assert "🟡" in render_coverage_line(10, 100)   # 10% → 접이식
    assert "⚪" in render_coverage_line(2, 100)    # 2% → 각주형
    assert render_coverage_line(0, 100) == ""      # 미확인 0건 → 표시 없음
    assert render_coverage_line(5, 0) == ""        # 상품 0개 → 표시 없음
