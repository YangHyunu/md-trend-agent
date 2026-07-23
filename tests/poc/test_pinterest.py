"""Pinterest v5 수요 어댑터 테스트. fixture는 2026-07-23 실 API 트리밍.

Pinterest 계약은 NAVER `{signals[], failures[]}`를 미러하되 스케일이 다르다(절대비교 금지).
time_series는 API가 `{date: int}` dict로 주므로 정렬해 series로 편다. keyword metrics의
빈 키워드는 응답 data[]에서 아예 부재 → 요청/응답 diff로 '코퍼스 미검출'을 실패 아닌
신호로 정직 표기(NAVER 검색량0 표기와 동형).
"""
import json
from pathlib import Path

import httpx

from poc import config, pinterest

_FIX = Path(__file__).parent / "fixtures"
_TRENDS = json.loads((_FIX / "pinterest_trends_top.json").read_text())
_KW = json.loads((_FIX / "pinterest_keyword_metrics.json").read_text())
_CAT = json.loads((_FIX / "pinterest_category_details.json").read_text())


def test_series_sorts_date_dict_into_ordered_points():
    pts = pinterest._series({"2025-08-02": 2, "2025-07-26": 1})
    assert pts == [{"period": "2025-07-26", "ratio": 1.0},
                   {"period": "2025-08-02", "ratio": 2.0}]
    assert pinterest._series({}) == []


def test_normalize_trends_maps_keyword_series_prediction():
    sigs = pinterest.normalize_trends(_TRENDS)
    assert len(sigs) == 3
    s0 = sigs[0]
    assert s0["source"] == "pinterest_trends"
    assert s0["group"] == "fdoc outfit hbcu"
    assert s0["series"][0]["period"] == "2025-07-26"
    assert s0["coverage_mismatch"] is False
    assert config.PINTEREST_REGION in s0["note"]     # US 리전 명기
    # has_prediction=True인 rush dresses만 예측 채워짐
    rush = [s for s in sigs if s["group"] == "rush dresses"][0]
    assert len(rush["prediction"]) == 4
    assert all(s["prediction"] == [] for s in sigs if s["group"] != "rush dresses")


def test_normalize_kw_metrics_present_keyword_carries_bucket():
    sigs = pinterest.normalize_kw_metrics(_KW, ["cardigan", "knitwear"])
    assert {s["group"] for s in sigs} == {"cardigan", "knitwear"}
    card = [s for s in sigs if s["group"] == "cardigan"][0]
    assert card["source"] == "pinterest_kw_metrics"
    assert "5M+" in card["note"]
    assert card["series"] == []                       # 볼륨은 시계열 아님


def test_normalize_kw_metrics_absent_keyword_is_corpus_gap_not_failure():
    # cashmere는 실 API에서 EMPTY(코퍼스 갭) — data[]에 부재
    sigs = pinterest.normalize_kw_metrics(_KW, ["cardigan", "cashmere", "merino wool"])
    gaps = [s for s in sigs if s["group"] in ("cashmere", "merino wool")]
    assert len(gaps) == 2
    for g in gaps:
        assert g["series"] == []
        assert "미검출" in g["note"]                   # 정직 표기, 실패 아님


def test_normalize_category_maps_timeseries():
    sigs = pinterest.normalize_category(_CAT)
    assert len(sigs) == 1
    s = sigs[0]
    assert s["source"] == "pinterest_category"
    assert s["group"] == "SWEATERS_AND_CARDIGANS"
    assert [p["period"] for p in s["series"]] == [
        "2025-07-19", "2025-07-26", "2025-08-02", "2025-08-09"]


def test_fetch_all_missing_token_degrades_to_failure(monkeypatch):
    monkeypatch.delenv("PINTEREST_ACCESS_TOKEN", raising=False)
    res = pinterest.fetch_all()
    assert res["signals"] == []
    assert res["failures"] and "PINTEREST_ACCESS_TOKEN" in res["failures"][0]["error"]


def test_fetch_all_wires_all_three_sources(monkeypatch):
    monkeypatch.setenv("PINTEREST_ACCESS_TOKEN", "pina_test")

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if "/top/" in p:
            return httpx.Response(200, json=_TRENDS)
        if "/keywords/metrics" in p:
            return httpx.Response(200, json=_KW)
        if "/product_categories/details" in p:
            return httpx.Response(200, json=_CAT)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler),
                          base_url=config.PINTEREST_BASE_URL)
    res = pinterest.fetch_all(client=client)
    srcs = {s["source"] for s in res["signals"]}
    assert srcs == {"pinterest_trends", "pinterest_kw_metrics", "pinterest_category"}
    assert res["failures"] == []
