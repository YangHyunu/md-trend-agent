"""NAVER API HUB 클라이언트. Search Trend + Shopping Insight."""
import json
import os
import sys

import httpx

from poc import config

RATIO_NOTE = "ratio는 각 요청 결과의 최대값을 100으로 둔 상대값. 서로 다른 요청 간 절대 비교 금지."


def build_search_trend_payload(start: str, end: str) -> dict:
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "keywordGroups": config.SEARCH_KEYWORD_GROUPS,
        "gender": "f",
        "ages": config.SEARCH_TREND_AGES,
    }


def build_shopping_category_payload(start: str, end: str) -> dict:
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "category": [{"name": config.SHOPPING_CAT_NAME, "param": [config.SHOPPING_CAT_ID]}],
        "gender": "f",
        "ages": config.SHOPPING_AGES,
    }


def build_shopping_keyword_payload(start: str, end: str) -> dict:
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "category": config.SHOPPING_CAT_ID,
        "keyword": [{"name": kw, "param": [kw]} for kw in config.SHOPPING_KEYWORDS],
        "gender": "f",
        "ages": config.SHOPPING_AGES,
    }


def _normalize(raw: dict, source: str, coverage_mismatch: bool) -> list[dict]:
    signals = []
    for r in raw.get("results", []):
        signals.append({
            "source": source,
            "group": r.get("title", ""),
            "series": r.get("data", []),
            "requested_segment": "25-39",
            "observed_segment": "20-39" if coverage_mismatch else "25-39",
            "coverage_mismatch": coverage_mismatch,
            "note": RATIO_NOTE,
        })
    return signals


CALLS = [
    ("search_trend", "/search-trend/v1/search", build_search_trend_payload, False),
    ("shopping_category", "/shopping/v1/categories", build_shopping_category_payload, True),
    ("shopping_keyword", "/shopping/v1/category/keywords", build_shopping_keyword_payload, True),
]


def fetch_all() -> dict:
    client_id = os.environ.get("NCP_API_HUB_CLIENT_ID")
    client_secret = os.environ.get("NCP_API_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"raw": {}, "signals": [], "failures": [{"call": "all", "error": "NCP_API_HUB_CLIENT_ID/SECRET 환경변수 없음"}]}

    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
        "Content-Type": "application/json",
    }
    start, end = config.period()
    result = {"raw": {}, "signals": [], "failures": []}
    calls_made = 0
    with httpx.Client(base_url=config.NAVER_BASE_URL, headers=headers, timeout=20) as client:
        for name, path, builder, mismatch in CALLS:
            if calls_made >= config.MAX_NAVER_CALLS:
                result["failures"].append({"call": name, "error": "NAVER 호출 예산 초과로 생략"})
                continue
            calls_made += 1
            try:
                resp = client.post(path, json=builder(start, end))
                resp.raise_for_status()
                raw = resp.json()
                result["raw"][name] = raw
                result["signals"].extend(_normalize(raw, name, mismatch))
            except Exception as e:
                result["failures"].append({"call": name, "error": f"{type(e).__name__}: {e}"})
    return result


def _offline_check() -> None:
    p = build_search_trend_payload("2026-05-25", "2026-07-20")
    assert p["ages"] == ["4", "5", "6"], "Search Trend 연령 코드 오류"
    assert len(p["keywordGroups"]) <= 5
    assert all(len(g["keywords"]) <= 20 for g in p["keywordGroups"])

    c = build_shopping_category_payload("2026-05-25", "2026-07-20")
    assert c["ages"] == ["20", "30"], "Shopping Insight 연령 코드 오류"
    assert len(c["category"]) <= 3

    k = build_shopping_keyword_payload("2026-05-25", "2026-07-20")
    assert len(k["keyword"]) <= 5
    assert all(len(x["param"]) == 1 for x in k["keyword"])

    fixture = {"results": [{"title": "캐시미어니트", "data": [{"period": "2026-06-01", "ratio": 100.0}]}]}
    sig = _normalize(fixture, "shopping_keyword", True)[0]
    assert sig["coverage_mismatch"] is True
    assert sig["observed_segment"] == "20-39"
    assert sig["requested_segment"] == "25-39"
    sig2 = _normalize(fixture, "search_trend", False)[0]
    assert sig2["coverage_mismatch"] is False
    print("naver offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
    else:
        config.OUT_DIR.mkdir(exist_ok=True)
        res = fetch_all()
        (config.OUT_DIR / "naver_raw.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"signals={len(res['signals'])} failures={len(res['failures'])}")
        for f in res["failures"]:
            print(" FAIL", f["call"], f["error"][:200])
