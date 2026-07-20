"""Markdown 보고서 렌더러. 코드가 렌더링 — LLM 자유 생성 금지 (POC_SPEC §6)."""
import sys
from datetime import date

from poc import config
from poc.analyze import AnalysisOutput

RATIO_WARNING = ("> **주의:** NAVER ratio는 각 요청 결과의 최대값을 100으로 둔 상대값입니다. "
                 "서로 다른 요청의 값을 절대량처럼 비교할 수 없습니다.")
COVERAGE_WARNING = ("> **주의:** Shopping Insight는 25~39세를 정확히 표현할 수 없어 "
                    "20~39세(coverage_mismatch) 데이터입니다.")


def _ids(evidence_ids: list[str]) -> str:
    return ", ".join(evidence_ids) if evidence_ids else "근거 없음"


def _cell(s: str) -> str:
    """Markdown 테이블 셀 이스케이프 — LLM 문자열의 |가 열을 깨뜨리지 않게."""
    return s.replace("|", "\\|")


def render_report(analysis: AnalysisOutput, naver: dict,
                  crawl_results: list[dict], evidence: list[dict]) -> str:
    L: list[str] = []
    a = config.ANALYSIS
    L.append(f"# 캐시미어·니트웨어 트렌드 보고서 (PoC)\n")
    L.append(f"- 생성일: {date.today().isoformat()}")
    L.append(f"- 조건: {a['category']} / {a['target']} / {a['price_range']} / 최근 {a['period_weeks']}주")
    L.append(f"- 중점: {a['focus']}\n")

    L.append("## 1. 핵심 요약\n")
    for t in analysis.trends[:3]:
        L.append(f"- [{t.phase}] {t.name} ({_ids(t.evidence_ids)})")
    for act in analysis.actions[:3]:
        L.append(f"- 액션: {act.recommendation} ({_ids(act.evidence_ids)})")
    L.append("")

    L.append("## 2. 수요 신호 (NAVER)\n")
    L.append(RATIO_WARNING)
    signals = naver.get("signals", [])
    if any(s["coverage_mismatch"] for s in signals):
        L.append(COVERAGE_WARNING)
    L.append("")
    for s in signals:
        series = s["series"]
        if not series:
            continue
        latest, peak = series[-1], max(series, key=lambda d: d["ratio"])
        L.append(f"- **{s['group']}** ({s['source']}, {s['observed_segment']}세): "
                 f"최근 {latest['period']} ratio {latest['ratio']}, "
                 f"기간 내 최고 {peak['period']} ratio {peak['ratio']}")
    if not signals:
        L.append("- NAVER 신호 없음 (수집 실패 — 7절 참고)")
    L.append("")

    L.append("## 3. Design Map\n")
    L.append("| 브랜드 | 핵심 아이템 | 컬러 | 소재 | 실루엣 | 디테일 | 가격대 | 근거 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in analysis.design_map:
        L.append(f"| {_cell(r.brand)} | {_cell(r.key_items)} | {_cell(r.colors)} | {_cell(r.materials)} | "
                 f"{_cell(r.silhouettes)} | {_cell(r.details)} | {_cell(r.price_range)} | {_ids(r.evidence_ids)} |")
    L.append("")

    L.append("## 4. 트렌드\n")
    for phase in ("상승", "주류", "포화", "둔화"):
        items = [t for t in analysis.trends if t.phase == phase]
        if items:
            L.append(f"### {phase}")
            for t in items:
                L.append(f"- **{t.name}**: {t.rationale} ({_ids(t.evidence_ids)})")
            L.append("")

    L.append("## 5. 상품 구성 공백과 기회\n")
    for g in analysis.gaps:
        L.append(f"- {g}")
    L.append("")

    L.append("## 6. MD 추천 액션\n")
    for i, act in enumerate(analysis.actions, 1):
        L.append(f"{i}. **{act.recommendation}** — {act.rationale} ({_ids(act.evidence_ids)})")
    L.append("")

    L.append("## 7. 데이터 한계와 수집 실패\n")
    for lim in analysis.limitations:
        L.append(f"- {lim}")
    failed = [r for r in crawl_results if not r["ok"]]
    if failed:
        L.append(f"\n수집 실패 URL {len(failed)}건:")
        for r in failed:
            L.append(f"- {r['url']} — {' '.join(r['error'].split())}")
    for f in naver.get("failures", []):
        L.append(f"- NAVER {f['call']} 실패 — {' '.join(f['error'].split())}")
    L.append("- PLUSH'MERE: Instagram — SNS 자동 수집 제외 (reference_only)")
    L.append("")

    L.append("## 8. 출처\n")
    L.append("| ID | URL | 브랜드 | 수집일 |")
    L.append("|---|---|---|---|")
    for e in evidence:
        L.append(f"| {e['id']} | {e['url']} | {e.get('brand') or '-'} | {e['fetched_at'][:10]} |")
    L.append("")
    return "\n".join(L)


def _offline_check() -> None:
    from poc.analyze import Action, AnalysisOutput, DesignMapRow, Trend
    analysis = AnalysisOutput(
        trends=[Trend(name="브러시드 캐시미어", phase="상승", rationale="r", evidence_ids=["E001"]),
                Trend(name="근거약한트렌드", phase="둔화", rationale="r2", evidence_ids=[])],
        design_map=[DesignMapRow(brand="Quince", key_items="아이템A|아이템B", colors="근거 없음",
                                 materials="캐시미어100", silhouettes="클래식", details="근거 없음",
                                 price_range="$49.90", evidence_ids=["E002"])],
        gaps=["컬러블록 부재"],
        actions=[Action(recommendation="a", rationale="b", evidence_ids=["E001"])],
        limitations=["표본 작음 — 추가 조사 필요"])
    naver = {"signals": [{"source": "shopping_keyword", "group": "캐시미어니트",
                          "series": [{"period": "2026-06-01", "ratio": 100.0}],
                          "requested_segment": "25-39", "observed_segment": "20-39",
                          "coverage_mismatch": True, "note": ""}],
             "failures": [{"call": "search_trend", "error": "401"}]}
    crawl = [{"url": "https://x.com", "ok": False, "text": "", "error": "timeout", "fetched_at": "t"}]
    ev = [{"id": "E001", "url": "https://extreme-cashmere.com/", "brand": "Extreme cashmere",
           "source_type": "official", "fetched_at": "2026-07-20T00:00:00"}]
    md = render_report(analysis, naver, crawl, ev)
    assert "상대값" in md, "ratio 주의문 누락"
    assert "20~39세" in md, "coverage_mismatch 주의문 누락"
    assert "근거 없음" in md
    assert "PLUSH'MERE" in md
    assert "https://x.com" in md and "timeout" in md, "실패 URL 누락"
    assert "| E001 |" in md, "출처 테이블 누락"
    assert "search_trend" in md and "401" in md, "NAVER 실패 표시 누락"
    assert "근거약한트렌드" in md and "근거 없음" in md.split("근거약한트렌드")[1][:80], "_ids 빈 리스트 폴백 미동작"
    row_line = [l for l in md.splitlines() if l.startswith("| Quince")][0]
    # 이스케이프된 파이프(\|)는 실제 열 구분자가 아니므로 제외하고 셀 수를 센다.
    assert row_line.replace("\\|", "").count("|") == 9, "파이프 이스케이프 실패로 열 수 불일치"
    assert "아이템A\\|아이템B" in md
    print("report offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
