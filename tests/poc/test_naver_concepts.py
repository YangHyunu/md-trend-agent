"""concepts→NAVER Search Trend 배치 배선 테스트 (SPEC_V3 §7). 네트워크 없음."""
import json

import httpx

from poc import config
from poc.naver import build_concept_trend_payload, fetch_concept_trends


def _concept(i: int) -> dict:
    return {"label_ko": f"컨셉{i}", "label_en": f"concept {i}",
            "naver_queries": [f"쿼리{i}"], "aliases": [], "category": "테마",
            "source_refs": ["a0000000001"], "rationale": "r"}


def _echo_handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    results = [{"title": g["groupName"], "data": [{"period": "2026-06-01", "ratio": 50.0}]}
               for g in payload["keywordGroups"]]
    return httpx.Response(200, json={"results": results})


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url=config.NAVER_BASE_URL)


def test_payload_respects_naver_limits():
    p = build_concept_trend_payload([_concept(i) for i in range(5)],
                                    "2026-05-25", "2026-07-20")
    assert len(p["keywordGroups"]) <= 5
    assert all(len(g["keywords"]) <= 20 for g in p["keywordGroups"])
    assert p["ages"] == ["4", "5", "6"] and p["gender"] == "f" and p["timeUnit"] == "week"
    assert p["keywordGroups"][0] == {"groupName": "컨셉0", "keywords": ["쿼리0"]}


def test_fetch_batches_of_five(monkeypatch):
    monkeypatch.setenv("NCP_API_HUB_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_API_HUB_CLIENT_SECRET", "secret")
    with _client(_echo_handler) as c:
        res = fetch_concept_trends([_concept(i) for i in range(12)], client=c)
    assert len(res["raw"]) == 3                       # ceil(12/5)
    assert len(res["signals"]) == 12
    assert res["signals"][0]["group"] == "컨셉0"
    assert res["signals"][0]["source"] == "concept_trend"
    assert res["signals"][0]["coverage_mismatch"] is False
    assert res["failures"] == []


def test_fetch_isolates_batch_failure(monkeypatch):
    monkeypatch.setenv("NCP_API_HUB_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_API_HUB_CLIENT_SECRET", "secret")

    def flaky(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["keywordGroups"][0]["groupName"] == "컨셉5":   # 2번째 배치 죽음
            return httpx.Response(500, text="boom")
        return _echo_handler(request)

    with _client(flaky) as c:
        res = fetch_concept_trends([_concept(i) for i in range(12)], client=c)
    assert len(res["signals"]) == 7                   # 배치1(5) + 배치3(2)
    assert len(res["failures"]) == 1
    assert res["failures"][0]["call"] == "concept_trend_b1"


def test_fetch_respects_call_budget(monkeypatch):
    monkeypatch.setenv("NCP_API_HUB_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_API_HUB_CLIENT_SECRET", "secret")
    with _client(_echo_handler) as c:
        res = fetch_concept_trends([_concept(i) for i in range(25)], client=c)
    assert len(res["raw"]) == config.MAX_CONCEPT_TREND_CALLS      # 4번째까지만 호출
    assert any("예산" in f["error"] for f in res["failures"])      # 5번째 배치는 기록


def test_fetch_without_env_returns_failure(monkeypatch):
    monkeypatch.delenv("NCP_API_HUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("NCP_API_HUB_CLIENT_SECRET", raising=False)
    res = fetch_concept_trends([_concept(0)])
    assert res["signals"] == [] and len(res["failures"]) == 1
