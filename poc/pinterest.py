"""Pinterest v5 수요 어댑터. NAVER `{signals[], failures[]}` 계약 미러 (별개 스케일).

세 축:
- pinterest_trends  : /v5/trends/keywords/{region}/top/growing — womens_fashion top50 성장 트렌드
- pinterest_kw_metrics: /v5/ad_accounts/{acct}/keywords/metrics — 임의 키워드 월간 검색량 버킷
- pinterest_category : /v5/trends/product_categories/details — 니트 카테고리 53주 시계열

주의: Pinterest ratio/volume은 NAVER와 절대비교 불가(다른 스케일·US 코퍼스). keyword
metrics의 빈 키워드는 응답에서 부재하므로 요청/응답 diff로 '코퍼스 미검출'을 실패
아닌 신호로 정직 표기(cashmere/merino류 갭). KR 리전 없어 US 프록시.
"""
import json
import os
import sys

import httpx

from poc import config

SCALE_NOTE = (f"Pinterest {config.PINTEREST_REGION} 수요. ratio/버킷은 NAVER와 "
              "스케일 상이 — 절대 비교 금지.")
_GAP_NOTE = f"Pinterest {config.PINTEREST_REGION} 코퍼스 미검출(코퍼스 갭). " + SCALE_NOTE


def _series(ts: dict) -> list[dict]:
    """API의 {date: int} dict를 정렬된 [{period, ratio}] 시계열로 편다."""
    return [{"period": k, "ratio": float(v)} for k, v in sorted((ts or {}).items())]


def _signal(source: str, group: str, series: list[dict], note: str,
            prediction: list[dict] | None = None) -> dict:
    return {
        "source": source,
        "group": group,
        "series": series,
        "requested_segment": config.PINTEREST_REGION,
        "observed_segment": config.PINTEREST_REGION,
        "coverage_mismatch": False,
        "note": note,
        "prediction": prediction or [],
    }


def normalize_trends(raw: dict) -> list[dict]:
    out = []
    for t in raw.get("trends", []):
        pred = _series(t.get("predicted_time_series")) if t.get("has_prediction") else []
        note = f"YoY {t.get('pct_growth_yoy')}%. " + SCALE_NOTE
        out.append(_signal("pinterest_trends", t.get("keyword", ""),
                           _series(t.get("time_series")), note, pred))
    return out


def normalize_kw_metrics(raw: dict, requested: list[str]) -> list[dict]:
    by_kw = {d.get("keyword"): d for d in raw.get("data", [])}
    out = []
    for kw in requested:
        d = by_kw.get(kw)
        if d is None:  # 응답에 부재 = 코퍼스 갭. 실패 아닌 정직 신호.
            out.append(_signal("pinterest_kw_metrics", kw, [], _GAP_NOTE))
            continue
        bucket = (d.get("metrics") or {}).get("KEYWORD_QUERY_VOLUME")
        note = f"월간 검색량 버킷 {bucket}. " + SCALE_NOTE
        out.append(_signal("pinterest_kw_metrics", kw, [], note))
    return out


def normalize_category(raw: list) -> list[dict]:
    out = []
    for c in raw or []:
        pred = _series(c.get("predicted_time_series")) if c.get("has_prediction") else []
        rel = c.get("related_searches") or []
        note = SCALE_NOTE + (f" 연관검색 {len(rel)}건." if rel else "")
        out.append(_signal("pinterest_category", c.get("product_category", ""),
                           _series(c.get("time_series")), note, pred))
    return out


def _get(client: httpx.Client, path: str, params: dict, name: str,
         result: dict, normalizer) -> None:
    try:
        resp = client.get(path, params=params)
        resp.raise_for_status()
        raw = resp.json()
        result["raw"][name] = raw
        result["signals"].extend(normalizer(raw))
    except Exception as e:
        result["failures"].append({"call": name, "error": f"{type(e).__name__}: {e}"})


def fetch_all(client: httpx.Client | None = None) -> dict:
    token = os.environ.get("PINTEREST_ACCESS_TOKEN")
    if not token:
        return {"raw": {}, "signals": [],
                "failures": [{"call": "all", "error": "PINTEREST_ACCESS_TOKEN 환경변수 없음"}]}

    result = {"raw": {}, "signals": [], "failures": []}
    own = client is None
    if own:
        client = httpx.Client(base_url=config.PINTEREST_BASE_URL, timeout=20)
    client.headers["Authorization"] = f"Bearer {token}"
    try:
        region = config.PINTEREST_REGION
        _get(client, f"/v5/trends/keywords/{region}/top/growing",
             {"interests": "womens_fashion", "include_prediction": "true", "limit": 25},
             "pinterest_trends", result, normalize_trends)
        kws = config.PINTEREST_KW_METRICS_KEYWORDS
        _get(client, f"/v5/ad_accounts/{config.PINTEREST_AD_ACCOUNT}/keywords/metrics",
             {"country_code": region, "keywords": ",".join(kws)},
             "pinterest_kw_metrics", result,
             lambda raw: normalize_kw_metrics(raw, kws))
        _get(client, "/v5/trends/product_categories/details",
             {"region": region, "product_categories": ",".join(config.PINTEREST_CATEGORIES)},
             "pinterest_category", result, normalize_category)
    finally:
        if own:
            client.close()
    return result


if __name__ == "__main__":
    config.OUT_DIR.mkdir(exist_ok=True)
    res = fetch_all()
    (config.OUT_DIR / "pinterest_raw.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"signals={len(res['signals'])} failures={len(res['failures'])}")
    for f in res["failures"]:
        print(" FAIL", f["call"], f["error"][:200], file=sys.stderr)
