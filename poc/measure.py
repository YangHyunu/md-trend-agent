"""결정론 측정 계층 (SPEC_V3 §7, §9.2) — 델타/방향 수학 + concept↔공급 매칭. LLM 없음."""
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
