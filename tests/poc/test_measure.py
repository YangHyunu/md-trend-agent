"""결정론 측정 수학 + concept↔공급 매칭 테스트 (SPEC_V3 §7, §9.2). LLM·네트워크 없음."""
from poc.measure import series_delta


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
