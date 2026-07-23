"""결정론 측정 수학 + concept↔공급 매칭 테스트 (SPEC_V3 §7, §9.2). LLM·네트워크 없음."""
from datalayer.records import ProductRecord
from poc.measure import concept_facets, match_supply, series_delta


def _series(ratios: list[float]) -> list[dict]:
    return [{"period": f"2026-06-{i+1:02d}", "ratio": r} for i, r in enumerate(ratios)]


def test_series_delta_up():
    d = series_delta(_series([10, 10, 10, 10, 20, 20, 20, 20]))
    assert d == {"delta_pct": 100.0, "direction": "up",
                 "recent_mean": 20.0, "prior_mean": 10.0}


def test_series_delta_down_and_flat():
    assert series_delta(_series([20, 20, 20, 20, 10, 10, 10, 10]))["direction"] == "down"
    d = series_delta(_series([10, 10, 10, 10, 10.5, 10.5, 10.5, 10.5]))
    assert d["direction"] == "flat" and d["delta_pct"] == 5.0


def test_series_delta_small_base_caps_percent():
    # 직전4주 평균 < 3 → 퍼센트 과장 금지(SPEC_V3 §9.2) — delta_pct 산출 안 함
    d = series_delta(_series([0, 1, 0, 2, 30, 30, 30, 30]))
    assert d["direction"] == "small_base" and d["delta_pct"] is None
    assert d["prior_mean"] == 0.75


def test_series_delta_zero_prior_is_small_base():
    d = series_delta(_series([0, 0, 0, 0, 5, 5, 5, 5]))
    assert d["direction"] == "small_base" and d["delta_pct"] is None


def test_series_delta_insufficient_points():
    # 8포인트 미만 — 판정 불가를 0%로 표현하지 않는다(V2 §8.7 정신)
    d = series_delta(_series([10, 20, 30]))
    assert d == {"delta_pct": None, "direction": "insufficient",
                 "recent_mean": None, "prior_mean": None}
    assert series_delta([])["direction"] == "insufficient"


def _rec(**kw) -> ProductRecord:
    base = dict(brand="b", url="https://x/p", item=None, colors_raw=[],
                price_native=None, currency=None, compare_at_native=None,
                on_sale=False, materials=[], published_at=None, source="t")
    base.update(kw)
    return ProductRecord(**base)


def _concept(**kw) -> dict:
    base = dict(label_ko="캐시미어 니트", label_en="cashmere knit", aliases=[],
                category="소재", naver_queries=["캐시미어 니트"],
                source_refs=["a0000000001"], rationale="r")
    base.update(kw)
    return base


def test_concept_facets_from_label_and_aliases():
    f = concept_facets(_concept(label_en="cashmere cardigan", aliases=["cardi"]))
    assert f["item"] == "Cardigan" and f["materials"] == ["cashmere"]
    # 'knit'는 ITEM_SYNONYMS에서 의도적으로 제외(기법어) — item은 None, 소재만 잡힘
    f2 = concept_facets(_concept(label_en="cashmere knit"))
    assert f2["item"] is None and f2["materials"] == ["cashmere"]
    # 컬러 concept → 8계열 매핑
    f3 = concept_facets(_concept(label_en="icy blue", category="컬러"))
    assert f3["color_family"] == "블루·네이비"


def test_match_supply_requires_all_facets():
    prods = [
        _rec(item="Cardigan", materials=["cashmere"]),
        _rec(item="Cardigan", materials=["wool"]),
        _rec(item="Sweater", materials=["cashmere"]),
    ]
    m = match_supply(_concept(label_en="cashmere cardigan"), prods)
    assert m["supply_count"] == 1 and m["unmeasurable"] is False


def test_match_supply_material_only_counts_all_items():
    prods = [_rec(item="Sweater", materials=["cashmere"]),
             _rec(item="Dress", materials=["cashmere"]),
             _rec(item="Sweater", materials=["wool"])]
    m = match_supply(_concept(label_en="cashmere knit"), prods)
    assert m["supply_count"] == 2


def test_match_supply_vocab_gap_is_unmeasurable_not_zero():
    # pointelle은 정규화 사전에 없음 → None(측정 불가). 0(공급 갭)과 구분 — 정직 표기
    m = match_supply(_concept(label_en="pointelle knit", label_ko="포인텔 니트",
                              aliases=["pointelle"]), [_rec(item="Sweater")])
    assert m["supply_count"] is None and m["unmeasurable"] is True
