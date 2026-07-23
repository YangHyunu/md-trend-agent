"""Markdown 리포트 렌더러 특성 테스트 (구 report._offline_check 승격)."""
from poc.report import render_report
from tests.poc import fixtures


def _render():
    return render_report(fixtures.analysis(), fixtures.naver(), fixtures.crawl(),
                         fixtures.evidence(), datalayer_aggregates=fixtures.datalayer_aggregates(),
                         steady=fixtures.steady())


def test_section_order_matches_md_workflow():
    md = _render()
    order = ["## 1. 한 장 요약", "## 2. 트렌드", "## 3. 시장 실측 스냅샷",
             "## 4. 브랜드 시그니처", "## 5. 국내 수요", "## 6. 상품 구성 공백", "## 7. 부록"]
    idx = [md.index(s) for s in order]
    assert idx == sorted(idx), f"섹션 순서 깨짐: {idx}"


def test_backed_trend_in_section2_with_crosscheck_and_link():
    md = _render()
    head = md.split("## 3.")[0]
    assert "브러시드 캐시미어 소재 세분화" in head, "backed 트렌드가 §2에 없음"
    assert "실측 대조: 소재 cashmere: Arch4(2) · 1/1몰" in md, "트렌드 실측 조인 실패"
    assert "[E014](https://www.harpersbazaar.com/x)" in md, "T2 근거 링크 실패"


def test_unbacked_trend_demoted_to_appendix():
    md = _render()
    assert "근거약한관찰" not in md.split("## 3.")[0], "근거없는 관찰이 §2에 남음(강등 실패)"
    assert md.index("근거약한관찰") > md.index("## 7. 부록"), "강등 트렌드가 부록에 없음"
    assert "미검증 관찰" in md, "미검증 관찰 헤딩 누락"
    assert "자동 매칭 축 없음" in md, "강등 트렌드 실측 조인 정직표기 누락"


def test_market_rollup_snapshot():
    md = _render()
    assert "지배축: 아이템 Sweater · 컬러 뉴트럴 · 실루엣 Relaxed" in md, "지배축 요약 실패"
    assert "가격 포지셔닝(중앙값·통화 상이): Arch4 GBP185" in md, "가격 사다리 실패"
    assert "█" in md, "막대 렌더 실패"


def test_brand_signature_line():
    md = _render()
    assert "**Arch4** (2) — 주력 Sweater · 뉴트럴 지배 · Relaxed · 중앙 GBP185" in md, "시그니처 줄 실패"
    assert "신상 출시: [Sweater 07-01](https://arch4.co.uk/p/x)" in md, "신상 상품 링크 실패"
    assert ("스테디셀러 신호: [This Best-Selling Arch4 Sweater]"
            "(https://www.realsimple.com/arch4-x) (커머스지)") in md, "스테디셀러 신호 렌더 실패"
    assert "Quince 스테디셀러 신호: [Best-Selling Quince Cashmere]" in md, \
        "미수집 브랜드 스테디셀러 신호 누락"
    assert "미수집(소스 미구현 갭):** Quince(지원 소스 없음)" in md, "미수집 브랜드 기록 실패"


def test_appendix_detail_pending_and_sources():
    md = _render()
    assert "<details>" in md and "브랜드 상세 실측" in md, "상세 실측 접기 누락"
    assert "🔴 아이템 1건(50%)" in md, "확인대기 통합줄(≥20%=🔴) 렌더 실패 (MDA-7)"
    assert "Camel(2)" in md, "상세 컬러 top 렌더 실패"
    assert "### 출처" in md and "| E014 |" in md and "T2 에디토리얼" in md, "출처 권위 테이블 누락"


def test_naver_warnings_and_blog_isolation():
    md = _render()
    assert "상대값" in md and "20~39세" in md, "NAVER 주의문 누락"
    assert "국내 웹 참고" in md and "[E017](https://m.blog.naver.com/xxx/1)" in md, "국내 참고 격리 누락"


def test_failure_records():
    md = _render()
    assert "https://x.com" in md and "timeout" in md, "실패 URL 누락"
    assert "search_trend" in md and "401" in md, "NAVER 실패 표시 누락"
    assert "PLUSH'MERE" in md


def test_no_datalayer_omits_market_sections():
    no_dl = render_report(fixtures.analysis(), fixtures.naver(), fixtures.crawl(),
                          fixtures.evidence())
    assert "## 3. 시장 실측 스냅샷" not in no_dl and "## 4. 브랜드 시그니처" not in no_dl, \
        "aggregates 없을 때 실측 섹션이 나옴"
