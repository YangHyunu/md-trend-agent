"""Markdown 보고서 렌더러. 코드가 렌더링 — LLM 자유 생성 금지 (POC_SPEC §6)."""
import sys
from collections import Counter
from datetime import date

from poc import config
from poc.analyze import AnalysisOutput

RATIO_WARNING = ("> **주의:** NAVER ratio는 각 요청 결과의 최대값을 100으로 둔 상대값입니다. "
                 "서로 다른 요청의 값을 절대량처럼 비교할 수 없습니다.")
COVERAGE_WARNING = ("> **주의:** Shopping Insight는 25~39세를 정확히 표현할 수 없어 "
                    "20~39세(coverage_mismatch) 데이터입니다.")


def _ids(evidence_ids: list[str], urls: dict[str, str] | None = None) -> str:
    """E코드 나열. urls 주면 [E013](url) 클릭 링크로 — §8 출처와 즉시 연결."""
    if not evidence_ids:
        return "근거 없음"
    if not urls:
        return ", ".join(evidence_ids)
    return ", ".join(f"[{i}]({urls[i]})" if i in urls else i for i in evidence_ids)


def _cell(s: str) -> str:
    """Markdown 테이블 셀 이스케이프 — LLM 문자열의 |가 열을 깨뜨리지 않게."""
    return s.replace("|", "\\|")


def _fmt_counts(pairs: list) -> str:
    """[(name, count), ...] → 'name(count), ...'. 빈 리스트는 '근거 없음'."""
    return ", ".join(f"{_cell(str(n))}({c})" for n, c in pairs) if pairs else "근거 없음"


def _pending_line(agg: dict) -> str:
    """브랜드 블록 하단 통합 확인대기 줄 — 3단계 이모지(🔴≥20%/🟡5~20%/⚪<5%) 유지 (MDA-7)."""
    n = agg["count"]
    parts = []
    for label, key in (("아이템", "items_unmatched"), ("컬러계열", "colors_family_unmatched"),
                       ("실루엣", "silhouettes_unmatched")):
        u = agg.get(key, 0)
        if u <= 0:
            continue
        ratio = u / n
        emoji = "🔴" if ratio >= 0.20 else ("🟡" if ratio >= 0.05 else "⚪")
        parts.append(f"{emoji} {label} {u}건({round(ratio * 100)}%)")
    return ("⚠️ 확인 대기: " + " · ".join(parts) +
            " — 사람확인 큐(item_review_queue.json)") if parts else ""


# 한글 트렌드어 → datalayer 영어 어휘 (트렌드↔실측 조인용 최소 사전).
# 오매칭 위험 단어('울'⊂서울 등)는 일부러 제외 — 조인은 보수적으로.
_KO_EN = {
    "그레이": "grey", "네이비": "navy", "블랙": "black", "아이보리": "ivory",
    "카멜": "camel", "베이지": "beige", "브라운": "brown", "레드": "red", "핑크": "pink",
    "오버사이즈": "oversized", "크롭": "cropped", "청키": "chunky", "릴랙스": "relaxed",
    "가디건": "cardigan", "스웨터": "sweater", "베스트": "vest", "스카프": "scarf",
    "머플러": "scarf", "원피스": "dress", "터틀넥": "turtleneck",
    "캐시미어": "cashmere", "메리노": "merino", "모헤어": "mohair", "알파카": "alpaca",
}


def _is_domestic_blog(url: str) -> bool:
    """국내 개인 블로그/커뮤니티 — MD 판단 근거로 권위 부족, 참고용 표시 대상."""
    u = (url or "").lower()
    return any(d in u for d in ("blog.naver.com", "m.blog.naver.com",
                                "post.naver.com", "tistory.com", "cafe.naver.com"))


def _trend_crosscheck(text: str, aggregates: list[dict]) -> str:
    """트렌드 텍스트 → datalayer 어휘 매칭 → 벤치마크 실측 대조 한 줄 (MD 조인).

    글로벌 트렌드가 우리가 보는 몰들에서 실제 얼마나 노출되는지 코드로 대조.
    매칭 축 없으면 정성 트렌드로 정직하게 표기 — 억지 조인 금지.
    """
    from datalayer import fields as dl
    ok = [a for a in aggregates if a.get("count")]
    if not ok:
        return ""
    # 한글 어휘를 영어로 증강한 뒤 기존 매처 재사용 (아이템/실루엣/8계열/소재)
    blob = text + " " + " ".join(en for ko, en in _KO_EN.items() if ko in text)
    axes: list[tuple[str, str, str]] = []  # (집계키, 축레이블, 매칭값)
    item = dl.match_item(blob)
    if item:
        axes.append(("items_top", "아이템", item))
    for s in dl.extract_silhouettes(blob, [], ""):
        axes.append(("silhouettes_top", "실루엣", s))
    fam = dl.map_color_family(blob)
    if fam:
        axes.append(("colors_family_top", "컬러계열", fam))
    for m in dl.extract_materials(blob):
        axes.append(("materials_top", "소재", m))
    if not axes:
        return "  - 실측 대조: 자동 매칭 축 없음(정성 트렌드) — 벤치마크 수치 대조 불가"
    parts = []
    for key, label, value in axes:
        hits = [(a["brand"], c) for a in ok
                for n, c in (a.get(key) or []) if str(n).lower() == value.lower()]
        if hits:
            top = ", ".join(f"{b}({c})" for b, c in sorted(hits, key=lambda x: -x[1])[:4])
            parts.append(f"{label} {value}: {top} · {len(hits)}/{len(ok)}몰")
        else:
            parts.append(f"{label} {value}: 벤치마크 {len(ok)}몰 노출 0")
    return "  - 실측 대조: " + " / ".join(parts)


def _datalayer_section(aggregates: list[dict]) -> list[str]:
    """부록 상세: datalayer 코드계산 브랜드 블록 — 브랜드별 미니 테이블 (POC_SPEC §12.4).

    상위 헤딩은 호출자(§7 부록)가 붙인다.
    """
    L = ["> 가격은 **native 통화**(KRW 환산 = 통화 정규화 이후). 컬러는 **원색명 + 8계열**(원색명은 근거 보존, 계열은 매핑 후).",
         "> 코드가 직접 집계 — LLM 해석 아님. 비Shopify 몰은 소스 미구현으로 실패 기록.\n"]
    ok = [a for a in aggregates if a.get("count")]
    failed = [a for a in aggregates if not a.get("count")]
    for a in ok:
        cur = a.get("currency") or "?"
        p = a.get("price")
        nw = a["newness"]
        L.append(f"### {a['brand']} — {a['source']}, {a['count']}개 상품\n")
        L.append("| 필드 | 실측 |")
        L.append("|---|---|")
        if p:
            L.append(f"| 가격({cur}) | p25 {p['p25']} / p50 {p['p50']} / p75 {p['p75']} "
                     f"(최저 {p['min']}–최고 {p['max']}, n={p['n']}) · 세일 {round(a['sale_ratio']*100)}% |")
        L.append(f"| 컬러 | {_fmt_counts(a['colors_top'])} |")
        if a.get("colors_family_top"):
            L.append(f"| 8계열 | {_fmt_counts(a['colors_family_top'])} |")
        L.append(f"| 아이템 | {_fmt_counts(a['items_top'])} |")
        L.append(f"| 소재 | {_fmt_counts(a['materials_top'])} |")
        if a.get("silhouettes_top"):
            L.append(f"| 실루엣 | {_fmt_counts(a['silhouettes_top'])} |")
        L.append(f"| 신상 {nw['weeks']}주 | {nw['recent_count']}개, 최신 {nw['latest'] or '없음'} |")
        L.append("")
        pending = _pending_line(a)
        if pending:
            L.append(pending)
            L.append("")
    if failed:
        L.append("**미수집(소스 사다리 rung2-4 미구현 — 정직한 갭):**")
        for a in failed:
            L.append(f"- {a['brand']}: {a.get('failure') or '수집 0건'}")
        L.append("")
    return L


def _bar(pairs: list, topn: int = 5) -> str:
    """분포를 막대+% 한 줄로. 분모 = 전체 합(상위 topn만 표시). MD가 '그림'으로 읽게."""
    tot = sum(c for _, c in pairs) or 1
    out = []
    for n, c in pairs[:topn]:
        share = c / tot
        out.append(f"{_cell(str(n))} {'█' * max(1, round(share * 8))} {round(share * 100)}%")
    return " · ".join(out) if out else "근거 없음"


def _roll(aggregates: list[dict], key: str) -> list:
    """브랜드 across 카운트 합산 → most_common. (컬러계열/아이템/실루엣/소재는 상품수 합산 가능)."""
    c: Counter = Counter()
    for a in aggregates:
        for n, cnt in (a.get(key) or []):
            c[n] += cnt
    return c.most_common()


def _market_rollup_section(aggregates: list[dict]) -> list[str]:
    """§3 시장 실측 스냅샷 — 전 브랜드 롤업 통계 요약(막대). 개별 수치 아님."""
    ok = [a for a in aggregates if a.get("count")]
    if not ok:
        return []
    total = sum(a["count"] for a in ok)
    items, fams = _roll(ok, "items_top"), _roll(ok, "colors_family_top")
    sils, mats = _roll(ok, "silhouettes_top"), _roll(ok, "materials_top")
    top1 = lambda r: r[0][0] if r else "—"
    L = [f"## 3. 시장 실측 스냅샷 ({len(ok)}개 몰 · 상품 {total}개)\n",
         "> 벤치마크 몰 전체 롤업 — 코드 집계. 브랜드별 개별 수치는 §7 부록.\n",
         f"**지배축: 아이템 {top1(items)} · 컬러 {top1(fams)} · 실루엣 {top1(sils)} · 소재 {top1(mats)}**\n",
         f"- 아이템: {_bar(items)}",
         f"- 컬러계열: {_bar(fams, 8)}",
         f"- 실루엣: {_bar(sils)}",
         f"- 소재: {_bar(mats)}"]
    ladder = sorted(((a["brand"], a["price"]["p50"], a.get("currency") or "?")
                     for a in ok if a.get("price")), key=lambda x: x[1])
    if ladder:
        L.append("- 가격 포지셔닝(중앙값·통화 상이): "
                 + " · ".join(f"{b} {cur}{p:.0f}" for b, p, cur in ladder))
    L.append("")
    return L


def _brand_signature_section(aggregates: list[dict],
                             steady: dict | None = None) -> list[str]:
    """§4 브랜드 시그니처 — 브랜드당 한 줄 프로필(주력·지배축·가격·신상·스테디셀러)."""
    steady = steady or {}
    ok = [a for a in aggregates if a.get("count")]
    failed = [a for a in aggregates if not a.get("count")]
    L = ["## 4. 브랜드 시그니처\n",
         "> 브랜드당 한 줄 = 주력 아이템·지배 컬러/실루엣·가격 중앙값·신상. 전체 필드는 §7 부록. "
         "스테디셀러 = 웹 판매신호(커머스지·공식) — 주1회 수집.\n"]
    for a in ok:
        top_items = ", ".join(n for n, _ in (a.get("items_top") or [])[:2]) or "—"
        fam = (a.get("colors_family_top") or [["—"]])[0][0]
        sils = ", ".join(n for n, _ in (a.get("silhouettes_top") or [])[:2]) or "—"
        p, cur = a.get("price"), a.get("currency") or "?"
        price = (f"중앙 {cur}{p['p50']:.0f}(세일 {round(a['sale_ratio'] * 100)}%)"
                 if p else "가격 미상")
        nw = a["newness"]
        line = (f"- **{_cell(a['brand'])}** ({a['count']}) — 주력 {_cell(top_items)} · "
                f"{_cell(fam)} 지배 · {_cell(sils)} · {price} · "
                f"최근{nw['weeks']}주 {nw['recent_count']}신상")
        newest = a.get("newest") or []
        if newest:
            links = ", ".join(f"[{_cell(p.get('item') or '상품')} {p['published_at'][5:]}]({p['url']})"
                              for p in newest)
            line += f"\n  - 신상 출시: {links}"
        hits = (steady.get(a["brand"]) or {}).get("hits") or []
        if hits:
            links = ", ".join(f"[{_cell(h['title'][:40])}]({h['url']}) ({h['authority']})"
                              for h in hits)
            line += f"\n  - 스테디셀러 신호: {links}"
        L.append(line)
    if failed:
        L.append("")
        L.append("**미수집(소스 미구현 갭):** "
                 + ", ".join(f"{a['brand']}({a.get('failure') or '0건'})" for a in failed))
        # 실측은 없어도 웹 판매신호는 노출 — 미수집 브랜드에 대한 유일한 시그널
        for a in failed:
            hits = (steady.get(a["brand"]) or {}).get("hits") or []
            if hits:
                links = ", ".join(f"[{_cell(h['title'][:40])}]({h['url']}) ({h['authority']})"
                                  for h in hits)
                L.append(f"  - {_cell(a['brand'])} 스테디셀러 신호: {links}")
    L.append("")
    return L


def render_report(analysis: AnalysisOutput, naver: dict,
                  crawl_results: list[dict], evidence: list[dict],
                  datalayer_aggregates: list[dict] | None = None,
                  steady: dict | None = None) -> str:
    L: list[str] = []
    a = config.ANALYSIS
    ev_urls = {e["id"]: e["url"] for e in evidence}  # E코드 → 출처 링크 (§8과 연결)
    L.append(f"# 캐시미어·니트웨어 트렌드 보고서 (PoC)\n")
    L.append(f"- 생성일: {date.today().isoformat()}")
    L.append(f"- 조건: {a['category']} / {a['target']} / {a['price_range']} / 최근 {a['period_weeks']}주")
    L.append(f"- 중점: {a['focus']}\n")

    def _domestic_only(t) -> str:
        """근거가 전부 국내 개인 블로그인 트렌드 — MD 판단 근거로 부족, 마커 부착."""
        if t.evidence_ids and all(_is_domestic_blog(ev_urls.get(i, "")) for i in t.evidence_ids):
            return " ⚠️ *국내 블로그 단독 근거 — 참고용*"
        return ""

    # 근거(T1·T2) 있는 트렌드만 헤드라인. 근거 없는 관찰은 §7 부록으로 강등.
    backed = [t for t in analysis.trends if t.evidence_ids]
    demoted = [t for t in analysis.trends if not t.evidence_ids]

    L.append("## 1. 한 장 요약\n")
    if backed:
        for t in backed[:3]:
            L.append(f"- **뜨는 것**: [{t.phase}] {t.name} ({_ids(t.evidence_ids, ev_urls)}){_domestic_only(t)}")
    else:
        L.append("- **뜨는 것**: 이번 수집엔 T1·T2 권위 근거 트렌드 없음 → §3 시장 실측·§7 미검증 관찰 참고")
    for act in analysis.actions[:3]:
        L.append(f"- **MD 액션**: {act.recommendation}")
    L.append("")

    # MD 워크플로우 ①: 트렌드 — 권위 근거(T1·T2)만. 각 트렌드에 벤치마크 실측 조인.
    L.append("## 2. 트렌드 (권위 근거 T1·T2)\n")
    L.append("> 업계지·에디토리얼 근거가 있는 트렌드만. 근거 없는 관찰은 §7 부록. "
             "각 줄 아래 **실측 대조** = 벤치마크 몰에서 실제 노출(코드 조인).\n")
    if backed:
        for phase in ("상승", "주류", "포화", "둔화"):
            items = [t for t in backed if t.phase == phase]
            if not items:
                continue
            L.append(f"### {phase}")
            for t in items:
                L.append(f"- **{t.name}**: {t.rationale} "
                         f"({_ids(t.evidence_ids, ev_urls)}){_domestic_only(t)}")
                cross = _trend_crosscheck(f"{t.name} {t.rationale}", datalayer_aggregates or [])
                if cross:
                    L.append(cross)
            L.append("")
    else:
        L.append("_권위 근거 트렌드 0건 — 크롤이 T1·T2 매체를 못 잡음. "
                 "시장 방향은 §3 실측으로 판단._\n")

    # MD 워크플로우 ②: 시장 실측 스냅샷(통계 요약) + 브랜드 시그니처
    if datalayer_aggregates:
        L.extend(_market_rollup_section(datalayer_aggregates))
        L.extend(_brand_signature_section(datalayer_aggregates, steady))

    # MD 워크플로우 ③: 국내 수요 — 한국서 먹히나 (데이터랩 정량 + 국내 웹 참고)
    L.append("## 5. 국내 수요 신호 (NAVER 데이터랩)\n")
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
        L.append("- NAVER 신호 없음 (수집 실패 — §7 부록 참고)")
    L.append("")
    domestic = [e for e in evidence if _is_domestic_blog(e.get("url", ""))]
    if domestic:
        L.append("**국내 웹 참고(개인 블로그 — 판단 근거 아님, 소비자 반응 참고만):**")
        for e in domestic:
            L.append(f"- [{e['id']}]({e['url']})")
        L.append("")

    # MD 워크플로우 ④: 갭 → 액션
    L.append("## 6. 상품 구성 공백 & MD 액션\n")
    L.append("**공백:**")
    for g in analysis.gaps:
        L.append(f"- {g}")
    L.append("\n**추천 액션:**")
    for i, act in enumerate(analysis.actions, 1):
        L.append(f"{i}. **{act.recommendation}** — {act.rationale} ({_ids(act.evidence_ids, ev_urls)})")
    L.append("")

    # §7 부록: 미검증 관찰 + 상세 실측(접기) + 출처 + 한계
    L.append("## 7. 부록\n")
    if demoted:
        L.append("### 미검증 관찰 (권위 근거 없음 — 참고만)\n")
        L.append("> 권위 매체(T1·T2) 근거가 없어 트렌드로 확정 못 함. 단, 벤치마크 실측 대조는 유효.\n")
        for t in demoted:
            L.append(f"- [{t.phase}] **{t.name}**: {t.rationale}{_domestic_only(t)}")
            cross = _trend_crosscheck(f"{t.name} {t.rationale}", datalayer_aggregates or [])
            if cross:
                L.append(cross)
        L.append("")

    if datalayer_aggregates:
        L.append("### 브랜드 상세 실측 (datalayer, Shopify 직수집)\n")
        L.append("<details><summary>펼치기 — 브랜드별 전체 필드 실측 + 확인 대기 큐</summary>\n")
        L.extend(_datalayer_section(datalayer_aggregates))
        L.append("</details>\n")

    L.append("### 출처\n")
    L.append("> 권위 티어: T1 업계지 · T2 에디토리얼 = 트렌드 근거 / T3 공식몰 = 벤치마크 실측 / T4 저권위 = 참고만.\n")
    L.append("| ID | 권위 | URL | 브랜드 | 수집일 |")
    L.append("|---|---|---|---|---|")
    for e in evidence:
        auth = e.get("authority") or ("T3 공식몰" if e.get("brand") else "T4 저권위")
        L.append(f"| {e['id']} | {auth} | {e['url']} | {e.get('brand') or '-'} | {e['fetched_at'][:10]} |")
    L.append("")

    L.append("### 데이터 한계와 수집 실패\n")
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
    return "\n".join(L)


def _offline_check() -> None:
    from poc.analyze import Action, AnalysisOutput, Trend
    analysis = AnalysisOutput(
        trends=[Trend(name="브러시드 캐시미어 소재 세분화", phase="상승",
                      rationale="에디토리얼이 캐시미어 소재 세분화를 지목", evidence_ids=["E014"]),
                Trend(name="근거약한관찰", phase="둔화",
                      rationale="정성 관찰 — 자동매칭 축 없음", evidence_ids=[])],
        design_map=[],  # §3 매트릭스 폐기 — 더 이상 렌더 안 함
        gaps=["컬러블록 부재"],
        actions=[Action(recommendation="뉴트럴 스웨터 확대", rationale="시장 지배축",
                        evidence_ids=["E014"])],
        limitations=["표본 작음 — 추가 조사 필요"])
    naver = {"signals": [{"source": "shopping_keyword", "group": "캐시미어니트",
                          "series": [{"period": "2026-06-01", "ratio": 100.0}],
                          "requested_segment": "25-39", "observed_segment": "20-39",
                          "coverage_mismatch": True, "note": ""}],
             "failures": [{"call": "search_trend", "error": "401"}]}
    crawl = [{"url": "https://x.com", "ok": False, "text": "", "error": "timeout", "fetched_at": "t"}]
    ev = [{"id": "E014", "url": "https://www.harpersbazaar.com/x", "brand": None, "tier": 2,
           "authority": "T2 에디토리얼", "fetched_at": "2026-07-20T00:00:00"},
          {"id": "E017", "url": "https://m.blog.naver.com/xxx/1", "brand": None, "tier": 4,
           "authority": "T4 저권위", "fetched_at": "2026-07-20T00:00:00"}]
    dl = [{"brand": "Arch4", "source": "shopify", "count": 2, "failure": None,
           "currency": "GBP", "price": {"min": 130.0, "max": 240.0, "p25": 150.0,
                                        "p50": 185.0, "p75": 220.0, "n": 2},
           "sale_ratio": 0.5, "colors_top": [("Camel", 2)],
           "colors_family_top": [("뉴트럴", 2)], "silhouettes_top": [("Relaxed", 2)],
           "items_top": [("Sweater", 2)], "items_unmatched": 1,
           "materials_top": [("cashmere", 2)],
           "newness": {"weeks": 8, "recent_count": 1, "latest": "2026-07-01"},
           "newest": [{"url": "https://arch4.co.uk/p/x", "item": "Sweater",
                       "published_at": "2026-07-01"}]},
          {"brand": "Quince", "source": None, "count": 0, "failure": "지원 소스 없음"}]
    steady = {"Arch4": {"fetched_at": "2026-07-21", "hits": [
        {"url": "https://www.realsimple.com/arch4-x", "title": "This Best-Selling Arch4 Sweater",
         "tier": 4, "authority": "커머스지"}]},
        "Quince": {"fetched_at": "2026-07-21", "hits": [
            {"url": "https://www.realsimple.com/quince-y", "title": "Best-Selling Quince Cashmere",
             "tier": 4, "authority": "커머스지"}]}}
    md = render_report(analysis, naver, crawl, ev, datalayer_aggregates=dl, steady=steady)

    # 섹션 순서 = MD 워크플로우 (요약→트렌드→시장실측→브랜드시그니처→국내→갭·액션→부록)
    order = ["## 1. 한 장 요약", "## 2. 트렌드", "## 3. 시장 실측 스냅샷",
             "## 4. 브랜드 시그니처", "## 5. 국내 수요", "## 6. 상품 구성 공백", "## 7. 부록"]
    idx = [md.index(s) for s in order]
    assert idx == sorted(idx), f"섹션 순서 깨짐: {idx}"

    # §2 트렌드: 권위 근거(T2) 있는 것만, 실측 조인 붙음
    assert "브러시드 캐시미어 소재 세분화" in md.split("## 3.")[0], "backed 트렌드가 §2에 없음"
    assert "실측 대조: 소재 cashmere: Arch4(2) · 1/1몰" in md, "트렌드 실측 조인 실패"
    assert "[E014](https://www.harpersbazaar.com/x)" in md, "T2 근거 링크 실패"

    # 강등: 근거 없는 관찰은 §2 아님, §7 부록 미검증 관찰에
    assert "근거약한관찰" not in md.split("## 3.")[0], "근거없는 관찰이 §2에 남음(강등 실패)"
    assert md.index("근거약한관찰") > md.index("## 7. 부록"), "강등 트렌드가 부록에 없음"
    assert "미검증 관찰" in md, "미검증 관찰 헤딩 누락"
    assert "자동 매칭 축 없음" in md, "강등 트렌드 실측 조인 정직표기 누락"

    # §3 시장 실측 스냅샷: 롤업 통계(막대)
    assert "지배축: 아이템 Sweater · 컬러 뉴트럴 · 실루엣 Relaxed" in md, "지배축 요약 실패"
    assert "가격 포지셔닝(중앙값·통화 상이): Arch4 GBP185" in md, "가격 사다리 실패"
    assert "█" in md, "막대 렌더 실패"

    # §4 브랜드 시그니처: 한 줄 프로필
    assert "**Arch4** (2) — 주력 Sweater · 뉴트럴 지배 · Relaxed · 중앙 GBP185" in md, "시그니처 줄 실패"
    assert "신상 출시: [Sweater 07-01](https://arch4.co.uk/p/x)" in md, "신상 상품 링크 실패"
    assert "스테디셀러 신호: [This Best-Selling Arch4 Sweater](https://www.realsimple.com/arch4-x) (커머스지)" \
        in md, "스테디셀러 신호 렌더 실패"
    assert "Quince 스테디셀러 신호: [Best-Selling Quince Cashmere]" in md, \
        "미수집 브랜드 스테디셀러 신호 누락"
    assert "미수집(소스 미구현 갭):** Quince(지원 소스 없음)" in md, "미수집 브랜드 기록 실패"

    # §7 부록: 상세 실측 접기 + 확인대기 + 출처(권위) + 한계
    assert "<details>" in md and "브랜드 상세 실측" in md, "상세 실측 접기 누락"
    assert "🔴 아이템 1건(50%)" in md, "확인대기 통합줄(≥20%=🔴) 렌더 실패 (MDA-7)"
    assert "Camel(2)" in md, "상세 컬러 top 렌더 실패"
    assert "### 출처" in md and "| E014 |" in md and "T2 에디토리얼" in md, "출처 권위 테이블 누락"

    # 국내 수요: NAVER 주의문 + 블로그 격리
    assert "상대값" in md and "20~39세" in md, "NAVER 주의문 누락"
    assert "국내 웹 참고" in md and "[E017](https://m.blog.naver.com/xxx/1)" in md, "국내 참고 격리 누락"

    # 실패 기록
    assert "https://x.com" in md and "timeout" in md, "실패 URL 누락"
    assert "search_trend" in md and "401" in md, "NAVER 실패 표시 누락"
    assert "PLUSH'MERE" in md

    # aggregates 없으면 §3·§4 미출력
    no_dl = render_report(analysis, naver, crawl, ev)
    assert "## 3. 시장 실측 스냅샷" not in no_dl and "## 4. 브랜드 시그니처" not in no_dl, \
        "aggregates 없을 때 실측 섹션이 나옴"
    print("report offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
