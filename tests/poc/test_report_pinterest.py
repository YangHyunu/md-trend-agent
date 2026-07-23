"""report_html Pinterest 섹션 테스트. pinterest 인자 있을 때만 렌더(조건부).

pinterest=None(기존 호출)이면 섹션 미출력 — 기존 numbered 섹션·테스트 불변.
"""
from poc.report_html import _pinterest_block, render_html
from tests.poc import fixtures


def _pin() -> dict:
    return {"signals": [
        {"source": "pinterest_trends", "group": "fall 2026 outfits",
         "series": [{"period": "2026-06-01", "ratio": 40.0},
                    {"period": "2026-06-08", "ratio": 100.0}],
         "requested_segment": "US", "observed_segment": "US",
         "coverage_mismatch": False, "note": "YoY 500%. Pinterest US 수요.",
         "prediction": []},
        {"source": "pinterest_kw_metrics", "group": "knitwear", "series": [],
         "requested_segment": "US", "observed_segment": "US",
         "coverage_mismatch": False,
         "note": "월간 검색량 버킷 5M+. Pinterest US 수요.", "prediction": []},
        {"source": "pinterest_kw_metrics", "group": "cashmere", "series": [],
         "requested_segment": "US", "observed_segment": "US",
         "coverage_mismatch": False,
         "note": "Pinterest US 코퍼스 미검출(코퍼스 갭).", "prediction": []},
        {"source": "pinterest_category", "group": "SWEATERS_AND_CARDIGANS",
         "series": [{"period": "2026-06-01", "ratio": 36.0},
                    {"period": "2026-06-08", "ratio": 46.0}],
         "requested_segment": "US", "observed_segment": "US",
         "coverage_mismatch": False, "note": "Pinterest US 수요.", "prediction": []},
    ], "failures": []}


def test_pinterest_block_renders_buckets_gaps_sparklines():
    html = _pinterest_block(_pin())
    assert "Pinterest" in html
    assert "5M+" in html and "knitwear" in html          # 버킷
    assert "미검출" in html and "cashmere" in html         # 코퍼스 갭 정직표기
    assert "SWEATERS_AND_CARDIGANS" in html
    assert 'class="spark"' in html                        # 트렌드/카테고리 스파크라인


def _render(pinterest=None):
    return render_html(fixtures.analysis(), fixtures.naver(), fixtures.crawl(),
                       fixtures.evidence(), datalayer_aggregates=fixtures.datalayer_aggregates(),
                       steady=fixtures.steady(), pinterest=pinterest)


def test_render_html_omits_pinterest_section_when_absent():
    out = _render(pinterest=None)
    assert "Pinterest" not in out                          # 기존 호출 불변


def test_render_html_includes_pinterest_section_when_present():
    out = _render(pinterest=_pin())
    assert "Pinterest" in out and "5M+" in out
    assert out.startswith("<!doctype html>") and out.endswith("</html>")
