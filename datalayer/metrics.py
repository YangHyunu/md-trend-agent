"""커버리지 스코어카드 (MDA-9). 새 측정 없음 — brand_aggregate 산출물 재조합만.

Loop: measure → 가장 낮은 셀 = 다음 작업 → 구현 → re-measure.
커버리지는 proxy — 인사이트 정합성은 ground truth 없이 못 잼.
"""
import json
from pathlib import Path

# 필드명 → aggregate의 unmatched 키 (brand_aggregate가 이미 계산)
_FIELD_UNMATCHED = {
    "item": "items_unmatched",
    "color_family": "colors_family_unmatched",
    "silhouette": "silhouettes_unmatched",
}


def collect_metrics(aggregates: list[dict]) -> dict:
    """brand_aggregate dict 리스트 → 검진표 dict (fields/sources/freshness)."""
    ok = [a for a in aggregates if a.get("count")]
    total_products = sum(a["count"] for a in ok)

    fields: dict = {}
    if ok:
        for field, key in _FIELD_UNMATCHED.items():
            unmatched = sum(a.get(key, 0) for a in ok)
            per_brand = [
                (a["brand"], round(1 - a.get(key, 0) / a["count"], 2)) for a in ok
            ]
            worst = min(per_brand, key=lambda x: x[1])
            fields[field] = {
                "overall": round(1 - unmatched / total_products, 2),
                "worst": [worst[0], worst[1]],
            }

    dated = [(a["brand"], a["newness"]["latest"]) for a in ok
             if a.get("newness", {}).get("latest")]
    stalest = min(dated, key=lambda x: x[1]) if dated else None

    return {
        "fields": fields,
        "sources": {"ok": len(ok), "total": len(aggregates)},
        "freshness": {"stalest": [stalest[0], stalest[1]] if stalest else None},
    }


def append_history(path: str | Path, metrics: dict, *, ts: str) -> None:
    """metrics_history.jsonl에 1줄 append — 시간축 추세용."""
    row = {"ts": ts, **metrics}
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
