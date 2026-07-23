"""리포트 렌더러 공용 입력 fixture (Markdown·HTML 두 렌더러가 공유).

이전에는 report.py·report_html.py 각자의 `_offline_check`에 같은 데이터가 복사돼 있었고
문구가 서로 drift했다. 여기로 단일화 — 두 렌더러 테스트가 같은 입력을 소비한다.
데이터는 두 렌더러의 모든 렌더 경로(hero 이미지·신상 썸네일·강등 트렌드·미수집 브랜드
steady 신호·NAVER 스파크라인·검색 0 브랜드)를 커버하도록 구성한 union이다.
"""
from poc.analyze import Action, AnalysisOutput, Trend


def analysis() -> AnalysisOutput:
    return AnalysisOutput(
        trends=[
            Trend(name="브러시드 캐시미어 소재 세분화", phase="상승",
                  rationale="에디토리얼이 캐시미어 소재 세분화를 지목", evidence_ids=["E014"]),
            Trend(name="근거약한관찰", phase="둔화",
                  rationale="정성 관찰 — 자동매칭 축 없음", evidence_ids=[]),
        ],
        design_map=[],
        gaps=["컬러블록 부재"],
        actions=[Action(recommendation="뉴트럴 스웨터 확대", rationale="시장 지배축",
                        evidence_ids=["E014"])],
        limitations=["표본 작음 — 추가 조사 필요"])


def naver() -> dict:
    return {"signals": [
        {"source": "shopping_keyword", "group": "캐시미어니트",
         "series": [{"period": "2026-06-01", "ratio": 100.0}],
         "requested_segment": "25-39", "observed_segment": "20-39",
         "coverage_mismatch": True, "note": ""},
        {"source": "item_search_trend", "group": "캐시미어 가디건",
         "series": [{"period": "2026-06-01", "ratio": 40.0},
                    {"period": "2026-06-08", "ratio": 100.0},
                    {"period": "2026-06-15", "ratio": 70.0}],
         "requested_segment": "25-39", "observed_segment": "25-39",
         "coverage_mismatch": False, "note": ""},
        {"source": "search_trend", "group": "제로수요",
         "series": [{"period": "2026-06-01", "ratio": 0.0},
                    {"period": "2026-06-08", "ratio": 0.0}],
         "requested_segment": "25-39", "observed_segment": "25-39",
         "coverage_mismatch": False, "note": ""},
        {"source": "brand_search_trend", "group": "Arch4",
         "series": [{"period": "2026-06-01", "ratio": 88.0}],
         "requested_segment": "25-39", "observed_segment": "25-39",
         "coverage_mismatch": False, "note": ""},
        {"source": "brand_search_trend", "group": "Quince",
         "series": [],
         "requested_segment": "25-39", "observed_segment": "25-39",
         "coverage_mismatch": False, "note": ""},
    ], "failures": [{"call": "search_trend", "error": "401"}]}


def crawl() -> list[dict]:
    return [{"url": "https://x.com", "ok": False, "text": "", "error": "timeout",
             "fetched_at": "t"}]


def evidence() -> list[dict]:
    return [
        {"id": "E014", "url": "https://www.harpersbazaar.com/x", "brand": None, "tier": 2,
         "authority": "T2 에디토리얼", "image": "https://media.hb.com/hero.jpg",
         "title": "The Best Cashmere Sweaters of 2026",
         "fetched_at": "2026-07-20T00:00:00"},
        {"id": "E017", "url": "https://m.blog.naver.com/xxx/1", "brand": None, "tier": 4,
         "authority": "T4 저권위", "fetched_at": "2026-07-20T00:00:00"},
    ]


def datalayer_aggregates() -> list[dict]:
    return [
        {"brand": "Arch4", "source": "shopify", "count": 2, "failure": None,
         "currency": "GBP", "price": {"min": 130.0, "max": 240.0, "p25": 150.0,
                                      "p50": 185.0, "p75": 220.0, "n": 2},
         "sale_ratio": 0.5, "colors_top": [("Camel", 2)],
         "colors_family_top": [("뉴트럴", 2)], "silhouettes_top": [("Relaxed", 2)],
         "items_top": [("Sweater", 2)], "items_unmatched": 1,
         "materials_top": [("cashmere", 2)],
         "newness": {"weeks": 8, "recent_count": 1, "latest": "2026-07-01"},
         "newest": [{"url": "https://arch4.co.uk/p/x", "item": "Sweater",
                     "published_at": "2026-07-01", "image_url": "https://cdn.a.co/x.jpg"}]},
        {"brand": "Quince", "source": None, "count": 0, "failure": "지원 소스 없음"},
    ]


def steady() -> dict:
    return {
        "Arch4": {"fetched_at": "2026-07-21", "hits": [
            {"url": "https://www.realsimple.com/arch4-x",
             "title": "This Best-Selling Arch4 Sweater", "tier": 4, "authority": "커머스지"}]},
        "Quince": {"fetched_at": "2026-07-21", "hits": [
            {"url": "https://www.realsimple.com/quince-y",
             "title": "Best-Selling Quince Cashmere", "tier": 4, "authority": "커머스지"}]},
    }
