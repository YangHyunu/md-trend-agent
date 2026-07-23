"""머지 번들 (SPEC_V3 §7) — concepts + 축별 측정치 + CoverageMetrics 단일 JSON.

M3 LLM#2의 입력 계약이자 M4 concept_weekly 저장의 원천. 조립은 순수 함수 — I/O 없음.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from datalayer.aggregate import brand_aggregate
from datalayer.records import BrandExtractionResult
from poc.measure import concept_facets, match_supply, series_delta

SCHEMA_VERSION = "3.0"


class NaverMeasure(BaseModel):
    series: list[dict]
    delta_pct: float | None
    direction: str
    recent_mean: float | None
    prior_mean: float | None


class SupplyMeasure(BaseModel):
    supply_count: int | None      # None = 어휘 갭(측정 불가), 0 = 측정됐는데 공급 없음(갭 신호)
    facets: dict
    unmeasurable: bool


class ConceptMeasurement(BaseModel):
    concept: dict
    naver: NaverMeasure | None    # None = 축 실패/시그널 부재 (0과 구분)
    supply: SupplyMeasure | None
    editorial_count: int


class AxisCoverage(BaseModel):
    attempted: int
    succeeded: int
    ratio: float | None           # 분모 0 → None (V2 §8.7 — 0%로 표현 금지)
    failures: list[dict] = Field(default_factory=list)


class MergeBundle(BaseModel):
    schema_version: str = SCHEMA_VERSION
    iso_week: str
    generated_at: str
    concepts: list[ConceptMeasurement]
    pinterest_category: list[dict]
    supply_brands: list[dict]     # brand_aggregate 블록 (LLM#2 근거·M5 report 재사용)
    coverage: dict[str, AxisCoverage]


def iso_week(now: datetime) -> str:
    """Asia/Seoul 기준 business date의 ISO 주 (V2 §13.6)."""
    y, w, _ = now.astimezone(ZoneInfo("Asia/Seoul")).isocalendar()
    return f"{y}-W{w:02d}"


def editorial_count(concept: dict) -> int:
    """§6.2 ref 문법 — 기사 ref(a<sha10>)만 count, 웹서치(w{i}) 제외."""
    return sum(1 for r in concept.get("source_refs", []) if r.startswith("a"))


def _axis(attempted: int, succeeded: int, failures: list[dict]) -> AxisCoverage:
    ratio = round(succeeded / attempted, 2) if attempted else None
    return AxisCoverage(attempted=attempted, succeeded=succeeded,
                        ratio=ratio, failures=failures)


def _measurable(concept: dict) -> bool:
    """concept이 정규화 사전 facet을 하나라도 갖는지 — 공급축 실행 여부와 무관(어휘 기반)."""
    f = concept_facets(concept)
    return bool(f["item"] or f["materials"] or f["silhouettes"] or f["color_family"])


def assemble(concepts: list[dict],
             naver_result: dict,
             pinterest_result: dict,
             extraction_results: list[BrandExtractionResult],
             *, now: datetime,
             supply_error: str | None = None) -> MergeBundle:
    products = [p for r in extraction_results for p in r.products]
    by_group = {s["group"]: s for s in naver_result["signals"]}

    measured: list[ConceptMeasurement] = []
    for c in concepts:
        sig = by_group.get(c["label_ko"])
        naver = NaverMeasure(series=sig["series"], **series_delta(sig["series"])) if sig else None
        supply = SupplyMeasure(**match_supply(c, products)) if extraction_results else None
        measured.append(ConceptMeasurement(
            concept=c, naver=naver, supply=supply, editorial_count=editorial_count(c)))

    naver_batches = -(-len(concepts) // 5) if concepts else 0   # ceil
    supply_failures = [{"call": "supply", "error": supply_error}] if supply_error else [
        {"call": r.brand, "error": r.failure} for r in extraction_results if r.failure]
    coverage = {
        "naver": _axis(naver_batches, len(naver_result["raw"]), naver_result["failures"]),
        "pinterest": _axis(1, len(pinterest_result["raw"]), pinterest_result["failures"]),
        "supply": _axis(len(extraction_results),
                        sum(1 for r in extraction_results if r.failure is None), supply_failures),
        "concept_match": _axis(
            len(concepts),
            sum(1 for c in concepts if _measurable(c)),
            []),
    }
    return MergeBundle(
        iso_week=iso_week(now),
        generated_at=now.isoformat(),
        concepts=measured,
        pinterest_category=pinterest_result["signals"],
        supply_brands=[brand_aggregate(r) for r in extraction_results],
        coverage=coverage,
    )
