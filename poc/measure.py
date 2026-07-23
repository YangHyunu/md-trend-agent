"""결정론 측정 계층 (SPEC_V3 §7, §9.2) — 델타/방향 수학 + concept↔공급 매칭. LLM 없음."""
from datalayer import fields
from datalayer.records import ProductRecord
from poc import config


def series_delta(series: list[dict]) -> dict:
    """주간 series(period 오름차순) → 최근4주 vs 직전4주 델타/방향 (SPEC_V3 §9.2 첫 주 규칙).

    direction: up(▲) / down(▼) / flat(→) / small_base(△) / insufficient.
    - small_base: 직전4주 평균 < config.SMALL_BASE_MEAN — delta_pct 미산출(퍼센트 과장 금지).
    - insufficient: 포인트 < 8 — 판정 불가를 0%로 표현하지 않는다.
    M4의 concept_weekly.direction/delta_pct가 이 값을 그대로 저장한다.
    """
    ratios = [p["ratio"] for p in series]
    if len(ratios) < 8:
        return {"delta_pct": None, "direction": "insufficient",
                "recent_mean": None, "prior_mean": None}
    recent_mean = sum(ratios[-4:]) / 4
    prior_mean = sum(ratios[-8:-4]) / 4
    if prior_mean < config.SMALL_BASE_MEAN:
        return {"delta_pct": None, "direction": "small_base",
                "recent_mean": round(recent_mean, 2), "prior_mean": round(prior_mean, 2)}
    delta = (recent_mean / prior_mean - 1) * 100
    if delta >= config.DELTA_FLAT_BAND_PCT:
        direction = "up"
    elif delta <= -config.DELTA_FLAT_BAND_PCT:
        direction = "down"
    else:
        direction = "flat"
    return {"delta_pct": round(delta, 1), "direction": direction,
            "recent_mean": round(recent_mean, 2), "prior_mean": round(prior_mean, 2)}


def concept_facets(concept: dict) -> dict:
    """concept 라벨/알리아스 → 정규화 사전 facet (V2 §13.3 결정론 매칭).

    영문 텍스트만 유효 매칭 — 상품 정규화 필드가 영문 canonical이기 때문.
    한국어 alias는 사전에 안 걸려 무해하게 통과한다.
    """
    texts = [concept["label_en"], *concept.get("aliases", [])]
    item = None
    materials: list[str] = []
    silhouettes: list[str] = []
    color_family = None
    for t in texts:
        item = item or fields.match_item(t)
        for m in fields.extract_materials(t):
            if m not in materials:
                materials.append(m)
        for s in fields.extract_silhouettes(t, [], ""):
            if s not in silhouettes:
                silhouettes.append(s)
        color_family = color_family or fields.map_color_family(t)
    return {"item": item, "materials": materials,
            "silhouettes": silhouettes, "color_family": color_family}


def match_supply(concept: dict, products: list[ProductRecord]) -> dict:
    """facet AND 매칭 공급 count. facet 0개 = unmeasurable(None) — 0(공급 갭)과 구분.

    unmeasurable은 코퍼스가 사전보다 앞서간 어휘(예: pointelle) — 선행신호 후보이며
    CoverageMetrics(concept_match 축)에 집계된다. 사전 확장은 별도 작업.
    """
    facets = concept_facets(concept)
    if not (facets["item"] or facets["materials"] or facets["silhouettes"]
            or facets["color_family"]):
        return {"supply_count": None, "facets": facets, "unmeasurable": True}
    count = 0
    for p in products:
        if facets["item"] and p.item != facets["item"]:
            continue
        if facets["materials"] and not all(m in p.materials for m in facets["materials"]):
            continue
        if facets["silhouettes"] and not all(s in p.silhouettes for s in facets["silhouettes"]):
            continue
        if facets["color_family"] and facets["color_family"] not in p.colors_family:
            continue
        count += 1
    return {"supply_count": count, "facets": facets, "unmeasurable": False}
