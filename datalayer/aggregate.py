"""브랜드 집계 — 코드가 100% 확정, LLM 해석 불가 (POC_SPEC §12.4).

가격은 native 통화(KRW 환산 = 통화 정규화 #2 이후), 컬러는 원색명(8계열 매핑 = #3 이후).
"""
from collections import Counter
from datetime import date, timedelta

from datalayer.records import BrandExtractionResult


def _percentile(sorted_vals: list[float], q: float) -> float | None:
    """선형보간 백분위. sorted_vals는 오름차순 정렬 가정."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo), 2)


def brand_aggregate(result: BrandExtractionResult, *, as_of: date | None = None,
                    newness_weeks: int = 8, top_n: int = 8) -> dict:
    """BrandExtractionResult → 코드계산 브랜드 블록 dict. 상품 0건이면 count=0 + failure 유지."""
    as_of = as_of or date.today()
    prods = result.products
    agg: dict = {"brand": result.brand, "source": result.source,
                 "count": len(prods), "failure": result.failure}
    if not prods:
        return agg

    prices = sorted(p.price_native for p in prods if p.price_native is not None and p.price_native > 0)
    currencies = Counter(p.currency for p in prods if p.currency)
    agg["currency"] = currencies.most_common(1)[0][0] if currencies else None
    agg["price"] = {
        "min": prices[0], "max": prices[-1],
        "p25": _percentile(prices, 0.25),
        "p50": _percentile(prices, 0.50),
        "p75": _percentile(prices, 0.75),
        "n": len(prices),
    } if prices else None

    agg["sale_ratio"] = round(sum(1 for p in prods if p.on_sale) / len(prods), 2)
    agg["colors_top"] = Counter(c for p in prods for c in p.colors_raw).most_common(top_n)
    agg["items_top"] = Counter(p.item for p in prods if p.item).most_common(top_n)
    agg["items_unmatched"] = sum(1 for p in prods if not p.item)
    agg["materials_top"] = Counter(m for p in prods for m in p.materials).most_common(top_n)

    cutoff = (as_of - timedelta(weeks=newness_weeks)).isoformat()
    dated = [p.published_at for p in prods if p.published_at]
    agg["newness"] = {
        "weeks": newness_weeks,
        "recent_count": sum(1 for d in dated if d >= cutoff),
        "latest": max(dated) if dated else None,
    }
    return agg
