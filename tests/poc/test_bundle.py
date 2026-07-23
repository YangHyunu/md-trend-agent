"""머지 번들 스키마+조립 테스트 (SPEC_V3 §7). LLM·네트워크 없음."""
from datetime import datetime, timezone

from datalayer.records import BrandExtractionResult, ProductRecord
from poc.bundle import MergeBundle, assemble, editorial_count, iso_week

NOW = datetime(2026, 7, 23, 3, 0, tzinfo=timezone.utc)


def _rec(**kw) -> ProductRecord:
    base = dict(brand="b", url="https://x/p", item=None, colors_raw=[],
                price_native=None, currency=None, compare_at_native=None,
                on_sale=False, materials=[], published_at=None, source="t")
    base.update(kw)
    return ProductRecord(**base)


def _concept(**kw) -> dict:
    base = dict(label_ko="캐시미어 니트", label_en="cashmere knit", aliases=[],
                category="소재", naver_queries=["캐시미어 니트"],
                source_refs=["a0000000001", "w0", "a0000000002"], rationale="r")
    base.update(kw)
    return base


def _naver_result(label: str) -> dict:
    series = [{"period": f"2026-06-{i+1:02d}", "ratio": r}
              for i, r in enumerate([10, 10, 10, 10, 20, 20, 20, 20])]
    return {"raw": {"concept_trend_b0": {}},
            "signals": [{"source": "concept_trend", "group": label, "series": series,
                         "requested_segment": "25-39", "observed_segment": "25-39",
                         "coverage_mismatch": False, "note": "n"}],
            "failures": []}


_EMPTY = {"raw": {}, "signals": [], "failures": []}


def test_iso_week_uses_seoul_business_date():
    assert iso_week(NOW) == "2026-W30"


def test_editorial_count_counts_article_refs_only():
    # §6.2 ref 문법: 기사 a<sha10> / 웹서치 w{i}
    assert editorial_count(_concept()) == 2


def test_assemble_joins_axes_per_concept():
    concepts = [_concept(),
                _concept(label_ko="포인텔 니트", label_en="pointelle knit",
                         source_refs=["a0000000001"])]
    extraction = [
        BrandExtractionResult(brand="A", source="shopify",
                              products=[_rec(item="Sweater", materials=["cashmere"])]),
        BrandExtractionResult(brand="B", source=None, products=[], failure="죽음"),
    ]
    b = assemble(concepts, _naver_result("캐시미어 니트"), _EMPTY, extraction, now=NOW)
    assert isinstance(b, MergeBundle) and b.schema_version == "3.0"
    assert b.iso_week == "2026-W30"

    cash = b.concepts[0]
    assert cash.naver is not None
    assert cash.naver.direction == "up" and cash.naver.delta_pct == 100.0
    assert cash.supply.supply_count == 1
    assert cash.editorial_count == 2

    point = b.concepts[1]
    assert point.naver is None                      # 시그널 없음 = None (0과 구분)
    assert point.supply.unmeasurable is True        # 어휘 갭 정직 표기


def test_assemble_coverage_is_honest():
    concepts = [_concept()]
    extraction = [
        BrandExtractionResult(brand="A", source="shopify", products=[_rec()]),
        BrandExtractionResult(brand="B", source=None, products=[], failure="죽음"),
    ]
    b = assemble(concepts, _naver_result("캐시미어 니트"), _EMPTY, extraction, now=NOW)
    assert b.coverage["naver"].attempted == 1 and b.coverage["naver"].succeeded == 1
    assert b.coverage["supply"].attempted == 2 and b.coverage["supply"].succeeded == 1
    assert b.coverage["supply"].ratio == 0.5
    assert b.coverage["concept_match"].attempted == 1


def test_assemble_axis_death_still_builds_bundle():
    # M2 수용 기준: 축 실패 시에도 번들 생성 + CoverageMetrics 기록
    fail = {"raw": {}, "signals": [],
            "failures": [{"call": "concept_trend", "error": "환경변수 없음"}]}
    b = assemble([_concept()], fail, _EMPTY, [], now=NOW, supply_error="VPN 죽음")
    assert b.concepts[0].naver is None
    assert b.coverage["naver"].failures                       # 실패 사유 보존
    assert b.coverage["supply"].attempted == 0
    assert b.coverage["supply"].ratio is None                 # 분모 0 → None, 0% 아님(V2 §8.7)
    assert b.coverage["supply"].failures[0]["error"] == "VPN 죽음"


def test_bundle_round_trips_json():
    b = assemble([_concept()], _EMPTY, _EMPTY, [], now=NOW)
    restored = MergeBundle.model_validate_json(b.model_dump_json())
    assert restored.iso_week == b.iso_week
