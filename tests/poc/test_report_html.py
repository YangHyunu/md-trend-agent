"""HTML 리포트 렌더러 특성 테스트 (구 report_html._offline_check 승격)."""
from poc.report_html import render_html
from tests.poc import fixtures


def _render():
    return render_html(fixtures.analysis(), fixtures.naver(), fixtures.crawl(),
                       fixtures.evidence(), datalayer_aggregates=fixtures.datalayer_aggregates(),
                       steady=fixtures.steady())


def test_document_envelope():
    out = _render()
    assert out.startswith("<!doctype html>") and out.endswith("</html>")


def test_images_rendered():
    out = _render()
    assert '<img src="https://cdn.a.co/x.jpg"' in out, "신상 썸네일 누락"
    assert '<img src="https://media.hb.com/hero.jpg"' in out, "트렌드 og:image 누락"
    assert 'class="hero"' in out, "트렌드 대표 이미지 누락"


def test_demoted_trend_in_appendix():
    out = _render()
    assert "근거약한관찰" in out and "미검증 관찰" in out, "강등 트렌드 부록 누락"


def test_uncollected_brand_steady_signal():
    out = _render()
    assert "Best-Selling Quince Cashmere" in out, "미수집 브랜드 steady 신호 누락"


def test_evidence_labels_and_titles():
    out = _render()
    assert "T2 에디토리얼" in out and "1,902" not in out
    assert "Harper&#x27;s Bazaar" in out, "매체명 링크 라벨 누락"
    assert "The Best Cashmere Sweaters of 2026" in out, "기사 제목 누락"


def test_naver_sparklines_and_brand_join():
    out = _render()
    assert "벤치마크 브랜드 검색 수요" in out and "Arch4" in out, "브랜드 수요 누락"
    assert out.count('class="spark"') == 4, "스파크라인 누락 (all-zero 시리즈 포함)"
    assert "아이템 수요" in out and "캐시미어 가디건" in out, "아이템 수요 누락"
    assert "주력 Sweater" in out, "브랜드 시그니처 병기 누락"
    assert "검색량 미검출" in out and "Quince" in out, "검색량 0 브랜드 표기 누락"


def test_removed_and_absent_markers():
    out = _render()
    assert "실측 대조" not in out, "실측 대조(마크다운 전용) 유입"
    assert "미수집" not in out, "미수집(마크다운 전용) 유입"


def test_appendix_collapsibles():
    out = _render()
    assert out.count("<details>") >= 2, "부록 접기 누락"
