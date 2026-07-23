"""HTML 보고서 렌더러 — 코드가 렌더링, LLM 자유 생성 금지 (report.py의 HTML 짝).

이미지(신상 썸네일·기사 og:image)는 외부 URL <img> — 로컬 파일/일반 호스팅에서 보임.
report.py와 동일 데이터·동일 게이팅(backed/demoted) 소비. 스타일은 MD 대시보드-닥.
"""
import html as _html
from collections import Counter
from datetime import date

from poc import config, report

FAM_COLOR = {  # 8계열 시맨틱 스와치
    "뉴트럴": "#8b8b8f", "베이지·브라운": "#b08d5a", "블루·네이비": "#3a5a8a",
    "그린": "#5e8a5e", "레드·핑크": "#c06a7e", "옐로·오렌지": "#d1a24a",
    "퍼플": "#8a6aa8", "멀티·패턴": "linear-gradient(90deg,#c06a7e,#d1a24a,#5e8a5e,#3a5a8a)",
}
E = lambda s: _html.escape(str(s))

_CSS = """
    :root {
      --paper:#f5f6f7; --ink:#1a1d21; --muted:#6b7076; --line:#e2e4e7; --card:#ffffff;
      --accent:#34506b; --accent-soft:#e8edf2; --hot:#c0492f; --warn:#b8862a;
      --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
      --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    }
    @media (prefers-color-scheme:dark) {
      :root { --paper:#16181b; --ink:#e8eaed; --muted:#9aa0a6; --line:#2b2f34; --card:#1e2125;
        --accent:#7ba3c8; --accent-soft:#233240; --hot:#e07a5f; --warn:#d6a94a; }
    }
    :root[data-theme="dark"] { --paper:#16181b; --ink:#e8eaed; --muted:#9aa0a6; --line:#2b2f34; --card:#1e2125;
      --accent:#7ba3c8; --accent-soft:#233240; --hot:#e07a5f; --warn:#d6a94a; }
    :root[data-theme="light"] { --paper:#f5f6f7; --ink:#1a1d21; --muted:#6b7076; --line:#e2e4e7; --card:#ffffff;
      --accent:#34506b; --accent-soft:#e8edf2; --hot:#c0492f; --warn:#b8862a; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans);
      line-height:1.55; -webkit-font-smoothing:antialiased; }
    .wrap { max-width:820px; margin:0 auto; padding:48px 24px 96px; }
    header { border-bottom:2px solid var(--ink); padding-bottom:20px; margin-bottom:8px; }
    .eyebrow { font-family:var(--mono); font-size:11px; letter-spacing:.18em; text-transform:uppercase;
      color:var(--accent); margin:0 0 10px; }
    h1 { font-family:var(--serif); font-size:34px; line-height:1.15; margin:0 0 12px; text-wrap:balance; font-weight:600; }
    .meta { font-family:var(--mono); font-size:12.5px; color:var(--muted); display:flex; gap:18px; flex-wrap:wrap; }
    .meta b { color:var(--ink); font-variant-numeric:tabular-nums; }
    section { margin-top:44px; }
    h2 { font-family:var(--serif); font-size:13px; letter-spacing:.05em; text-transform:uppercase;
      color:var(--muted); font-weight:600; margin:0 0 4px; display:flex; align-items:baseline; gap:10px; }
    h2::before { content:attr(data-n); font-family:var(--mono); color:var(--accent); font-size:12px; }
    .lead { font-family:var(--serif); font-size:19px; line-height:1.4; margin:6px 0 20px; text-wrap:pretty; }
    .note { font-size:12.5px; color:var(--muted); margin:0 0 16px; }
    /* §1 summary */
    .summary { background:var(--card); border:1px solid var(--line); border-radius:4px; padding:22px 24px; }
    .summary .row { display:flex; gap:12px; padding:9px 0; border-bottom:1px solid var(--line); }
    .summary .row:last-child { border:0; }
    .summary .tag { font-family:var(--mono); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase;
      color:var(--accent); min-width:74px; padding-top:2px; }
    /* bars */
    .bars { display:flex; flex-direction:column; gap:7px; margin:14px 0 4px; }
    .bar-row { display:grid; grid-template-columns:120px 1fr 40px; align-items:center; gap:12px; font-size:13px; }
    .bar-label { color:var(--ink); }
    .bar-track { height:9px; background:var(--accent-soft); border-radius:5px; overflow:hidden; }
    .bar-fill { display:block; height:100%; border-radius:5px; }
    .bar-pct { font-family:var(--mono); font-size:12px; color:var(--muted); text-align:right; font-variant-numeric:tabular-nums; }
    .axis { font-family:var(--mono); font-size:12.5px; color:var(--muted); margin:18px 0 6px; letter-spacing:.02em; }
    .axis b { color:var(--accent); }
    .grp { font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:.1em;
      color:var(--muted); margin:20px 0 8px; }
    /* price ladder */
    .ladder { position:relative; margin:20px 0 8px; display:flex; flex-direction:column; gap:3px; }
    .lad { position:relative; height:24px; display:flex; align-items:center; }
    .lad-b { width:130px; font-size:12.5px; }
    .lad-bar { position:absolute; width:9px; height:9px; border-radius:50%; background:var(--accent);
      margin-left:130px; transform:translateX(-4px); }
    .lad-p { position:absolute; right:0; font-family:var(--mono); font-size:12px; color:var(--muted);
      font-variant-numeric:tabular-nums; }
    /* §4 cards */
    .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; margin-top:14px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:4px; padding:15px 16px; }
    .card-top { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:9px; }
    .card-top b { font-size:15px; font-family:var(--serif); }
    .count { font-family:var(--mono); font-size:11.5px; color:var(--muted); }
    .sig { font-size:12.5px; color:var(--ink); margin-bottom:10px; }
    .chip { display:inline-block; font-size:11px; padding:1px 8px; border:1px solid; border-radius:20px;
      margin-right:6px; }
    .k { font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
    .stats { display:flex; gap:14px; font-size:12.5px; font-variant-numeric:tabular-nums; flex-wrap:wrap; }
    .stats b { font-family:var(--mono); }
    .newest { margin-top:10px; padding-top:9px; border-top:1px solid var(--line); font-size:12px; }
    .thumbs { display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }
    .thumb { display:block; width:72px; text-decoration:none; }
    .hero { display:block; max-width:340px; margin-top:10px; text-decoration:none; }
    .hero img { width:100%; aspect-ratio:16/10; object-fit:cover; border-radius:4px;
      border:1px solid var(--line); display:block; }
    .hero-cap { display:block; font-family:var(--mono); font-size:10.5px; color:var(--muted);
      margin-top:5px; line-height:1.4; }
    .thumb img { width:100%; aspect-ratio:3/4; object-fit:cover; border-radius:3px;
      border:1px solid var(--line); display:block; }
    .th-cap { display:block; font-family:var(--mono); font-size:9.5px; color:var(--muted);
      margin-top:3px; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .new { text-decoration:none; color:var(--accent); }
    .new:hover { text-decoration:underline; }
    .nd { font-family:var(--mono); font-size:10.5px; color:var(--muted); }
    .flag-hot { color:var(--hot); font-weight:600; }
    .flag-warn { color:var(--warn); }
    .missing { font-size:12.5px; color:var(--muted); margin-top:14px; padding-top:12px; border-top:1px dashed var(--line); }
    /* trends */
    .phase { font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:.12em;
      margin:22px 0 10px; color:var(--accent); }
    .trend { border-left:2px solid var(--accent); padding:2px 0 2px 16px; margin-bottom:16px; }
    .trend.demo { border-left-color:var(--line); }
    .trend-head b { font-size:15px; }
    .trend p { margin:4px 0 8px; font-size:13.5px; color:var(--ink); }
    .ev { font-family:var(--mono); font-size:10.5px; text-decoration:none; color:var(--accent);
      border:1px solid var(--accent-soft); padding:1px 5px; border-radius:3px; margin-left:4px; white-space:nowrap; }
    .ev em { font-style:normal; color:var(--muted); }
    /* lists */
    ul { padding-left:0; list-style:none; margin:0; }
    .gaps li, .naver li { padding:6px 0 6px 18px; position:relative; font-size:13.5px; border-bottom:1px solid var(--line); }
    .gaps li::before { content:"→"; position:absolute; left:0; color:var(--accent); }
    .acts { counter-reset:a; }
    .acts li { counter-increment:a; padding:10px 0 10px 30px; position:relative; border-bottom:1px solid var(--line); font-size:13.5px; }
    .acts li::before { content:counter(a); position:absolute; left:0; top:10px; font-family:var(--mono);
      background:var(--accent); color:#fff; width:19px; height:19px; border-radius:50%; text-align:center;
      font-size:11px; line-height:19px; }
    .muted { color:var(--muted); }
    /* §5 spark rows */
    .sigrow { display:grid; grid-template-columns:1fr 150px 160px; gap:14px; align-items:center;
      padding:8px 0; border-bottom:1px solid var(--line); }
    .sig-label b { font-size:13.5px; }
    .sig-sub { display:block; font-size:11.5px; color:var(--muted); margin-top:1px; }
    .sig-age { font-family:var(--mono); font-size:10px; color:var(--muted); }
    .sig-num { font-family:var(--mono); font-size:11.5px; color:var(--muted); text-align:right;
      font-variant-numeric:tabular-nums; }
    .spark { display:block; }
    @media (max-width:560px) { .sigrow { grid-template-columns:1fr 120px; } .sig-num { display:none; } }
    .dom { margin-top:14px; font-size:12.5px; }
    .dom-label { font-family:var(--mono); font-size:10.5px; text-transform:uppercase; letter-spacing:.08em; color:var(--warn); }
    .dom a { color:var(--muted); }
    /* appendix */
    details { border:1px solid var(--line); border-radius:4px; margin-top:14px; }
    summary { cursor:pointer; padding:12px 16px; font-family:var(--mono); font-size:12px; color:var(--accent); }
    .tbl-wrap { overflow-x:auto; padding:0 16px 16px; }
    table { border-collapse:collapse; width:100%; font-size:12px; }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
    th { font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
    td { font-variant-numeric:tabular-nums; }
    tr.tier1 td:nth-child(2), tr.tier2 td:nth-child(2) { color:var(--accent); font-weight:600; }
    tr.tier4 td:nth-child(2) { color:var(--muted); }
    a:focus-visible, summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    footer { margin-top:56px; padding-top:16px; border-top:1px solid var(--line);
      font-family:var(--mono); font-size:11px; color:var(--muted); }
"""

PUB_NAMES = {  # 도메인 → 매체명 (링크 라벨. 미등록 도메인은 host 표기)
    "businessoffashion.com": "BoF", "voguebusiness.com": "Vogue Business", "wwd.com": "WWD",
    "vogue.com": "Vogue", "vogue.co.uk": "Vogue UK",
    "harpersbazaar.com": "Harper's Bazaar", "harpersbazaar.co.uk": "Harper's Bazaar UK",
    "elle.com": "Elle", "graziamagazine.com": "Grazia", "grazia.co.uk": "Grazia UK",
    "graziadaily.co.uk": "Grazia UK", "realsimple.com": "Real Simple", "instyle.com": "InStyle",
    "whowhatwear.com": "Who What Wear", "refinery29.com": "Refinery29",
    "glamour.com": "Glamour", "marieclaire.com": "Marie Claire",
}


def _pubname(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for d, name in PUB_NAMES.items():
        if host == d or host.endswith("." + d):
            return name
    return host



def _roll(ok, key):
    """집계 aggregate들의 (name, count) 리스트를 브랜드 합산해 most_common."""
    c = Counter()
    for a in ok:
        for n, cnt in (a.get(key) or []):
            c[n] += cnt
    return c.most_common()


def _bars(pairs, topn=8, swatch=False):
    """(name, count) → 가로 막대 HTML. swatch=True면 8계열 시맨틱 컬러."""
    tot = sum(c for _, c in pairs) or 1
    rows = []
    for n, c in pairs[:topn]:
        pct = round(c / tot * 100)
        color = FAM_COLOR.get(n, "var(--accent)") if swatch else "var(--accent)"
        bg = color if color.startswith("linear") else color
        rows.append(f'''<div class="bar-row">
              <span class="bar-label">{E(n)}</span>
              <span class="bar-track"><span class="bar-fill" style="width:{pct}%;background:{bg}"></span></span>
              <span class="bar-pct">{pct}%</span></div>''')
    return "\n".join(rows)


def _evlink(ids, ev_urls, ev_auth, ev_title):
    """근거 E-id들 → 매체명+티어 배지 링크. 부록 출처 테이블과 title로 연결."""
    out = []
    for i in ids:
        url = ev_urls.get(i, "#")
        tier = ev_auth.get(i, "").split()[0]  # "T2 에디토리얼" → "T2"
        tip = f'{i} · {ev_title.get(i) or url}'
        out.append(
            f'<a class="ev" href="{E(url)}" target="_blank" rel="noopener" title="{E(tip)}">'
            f'{E(_pubname(url))} <em>{E(tier)}</em></a>')
    return " ".join(out)


def _spark(ser, w=150, h=34):
    """주간 series → 인라인 SVG 스파크라인 (행당 단일 시리즈 — accent 단색, 범례 불요)."""
    vals = [d["ratio"] for d in ser]
    mx = max(vals) or 1
    n = len(vals)
    pts = [((i * w / (n - 1)) if n > 1 else 0.0,
            h - 3 - (v / mx) * (h - 6)) for i, v in enumerate(vals)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    px, py = pts[vals.index(max(vals))]  # mx는 0-division 방지용 합성값일 수 있음 — 실제 최대 인덱스 사용
    ex, ey = pts[-1]
    rng = f'{ser[0]["period"]} ~ {ser[-1]["period"]}'
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="주간 검색 추이 {E(rng)}">'
            f'<polyline points="{poly}" fill="none" stroke="var(--accent)" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="none" stroke="var(--accent)" stroke-width="1.5"/>'
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3" fill="var(--accent)"/></svg>')


def _sig_rows(sigs, extra=None):
    """NAVER 시그널들 → 스파크라인 행. extra는 group→부가라벨(브랜드 시그니처 병기)."""
    rows = []
    for s in sigs:
        ser = s["series"]
        if not ser:
            continue
        latest = ser[-1]["ratio"]
        peak = max(d["ratio"] for d in ser)
        sub = (extra or {}).get(s["group"], "")
        rows.append(f'''<div class="sigrow">
              <span class="sig-label"><b>{E(s["group"])}</b> <span class="sig-age">{E(s["observed_segment"])}세</span>
                {f'<span class="sig-sub">{E(sub)}</span>' if sub else ''}</span>
              {_spark(ser)}
              <span class="sig-num">최근 {round(latest, 1)} · 최고 {round(peak, 1)}</span></div>''')
    return "\n".join(rows)


def _no_data_note(sigs):
    """series가 빈 시그널 group들 → '검색량 미검출' 주석."""
    missing = [s["group"] for s in sigs if not s["series"]]
    return (f'<p class="note">검색량 미검출: {E(", ".join(missing))}</p>' if missing else "")


def _trend_section(backed, evidence, ev_urls, ev_auth, ev_title):
    """§2 권위 근거 트렌드 블록 (phase 순 + hero 이미지)."""
    trend_html = []
    for phase in ("상승", "주류", "포화", "둔화"):
        items = [t for t in backed if t.phase == phase]
        if not items:
            continue
        trend_html.append(f'<h3 class="phase phase-{phase}">{E(phase)}</h3>')
        for t in items:
            hero = next((e for e in evidence
                         if e["id"] in t.evidence_ids and e.get("image")), None)
            img_html = ""
            if hero:
                cap = (hero.get("title") or "")[:70]
                img_html = (
                    f'<a href="{E(hero["url"])}" target="_blank" rel="noopener" class="hero" '
                    f'title="{E(hero.get("title") or hero["url"])}">'
                    f'<img src="{E(hero["image"])}" alt="{E(hero.get("title") or hero["id"])}" loading="lazy">'
                    f'<span class="hero-cap">{E(cap)} — {E(_pubname(hero["url"]))}</span></a>')
            trend_html.append(f'''<div class="trend">
              <div class="trend-head"><b>{E(t.name)}</b> {_evlink(t.evidence_ids, ev_urls, ev_auth, ev_title)}</div>
              <p>{E(t.rationale)}</p>
              {img_html}</div>''')
    return "\n".join(trend_html) or '<p class="muted">권위 근거(T1·T2) 트렌드 0건 — §3 실측으로 판단.</p>'


def _price_ladder(ok):
    """§3 가격 포지셔닝 사다리 (중앙값 기준, 통화 상이)."""
    ladder = sorted(((a["brand"], a["price"]["p50"], a.get("currency") or "?")
                     for a in ok if a.get("price")), key=lambda x: x[1])
    lad_span = (ladder[-1][1] - ladder[0][1]) if ladder else 0  # 1개 브랜드면 0 → 좌측 고정
    lad_min = ladder[0][1] if ladder else 0
    return "".join(
        f'<div class="lad"><span class="lad-b">{E(b)}</span>'
        f'<span class="lad-bar" style="left:{((p - lad_min) / lad_span * 100) if lad_span else 0:.0f}%"></span>'
        f'<span class="lad-p">{E(cur)}{p:.0f}</span></div>' for b, p, cur in ladder)


def _brand_cards(ok, failed, steady):
    """§4 브랜드 카드 + 미수집 브랜드 steady 신호. (cards_html, failed_steady_html)."""
    cards = []
    for a in ok:
        top_items = ", ".join(n for n, _ in (a.get("items_top") or [])[:2]) or "—"
        fam = (a.get("colors_family_top") or [["—"]])[0][0]
        sils = ", ".join(n for n, _ in (a.get("silhouettes_top") or [])[:2]) or "—"
        p, cur = a.get("price"), a.get("currency") or "?"
        price = f"{cur}{p['p50']:.0f}" if p else "—"
        sale = round(a["sale_ratio"] * 100)
        nw = a["newness"]
        sale_cls = "flag-hot" if sale >= 20 else ("flag-warn" if sale >= 5 else "")
        stale = "flag-warn" if nw["recent_count"] == 0 else ""
        newest = a.get("newest") or []
        new_html = ""
        if newest:
            thumbs = "".join(
                f'<a href="{E(p["url"])}" target="_blank" rel="noopener" class="thumb">'
                f'<img src="{E(p["image_url"])}" alt="{E(p.get("item") or "상품")}" loading="lazy">'
                f'<span class="th-cap">{E(p.get("item") or "상품")} {E(p["published_at"][5:])}</span></a>'
                for p in newest if p.get("image_url"))
            if thumbs:
                new_html = f'<div class="newest"><span class="k">신상 출시</span><div class="thumbs">{thumbs}</div></div>'
            else:
                links = " · ".join(
                    f'<a class="new" href="{E(p["url"])}" target="_blank" rel="noopener">'
                    f'{E(p.get("item") or "상품")} <span class="nd">{E(p["published_at"][5:])}</span></a>'
                    for p in newest)
                new_html = f'<div class="newest"><span class="k">신상 출시</span> {links}</div>'
        shits = (steady.get(a["brand"]) or {}).get("hits") or []
        if shits:
            slinks = " · ".join(
                f'<a class="new" href="{E(h["url"])}" target="_blank" rel="noopener">'
                f'{E(h["title"][:38])} <span class="nd">{E(h["authority"])}</span></a>' for h in shits)
            new_html += f'<div class="newest"><span class="k">스테디셀러 신호</span> {slinks}</div>'
        cards.append(f'''<div class="card">
          <div class="card-top"><b>{E(a['brand'])}</b><span class="count">{a['count']}개</span></div>
          <div class="sig"><span class="chip" style="border-color:{FAM_COLOR.get(fam,'#999') if not FAM_COLOR.get(fam,'').startswith('linear') else '#999'}">{E(fam)}</span>
            <span class="k">주력</span> {E(top_items)} · <span class="k">실루엣</span> {E(sils)}</div>
          <div class="stats">
            <span><span class="k">중앙가</span> <b>{E(price)}</b></span>
            <span class="{sale_cls}"><span class="k">세일</span> {sale}%</span>
            <span class="{stale}"><span class="k">최근8주</span> {nw['recent_count']}신상</span>
          </div>{new_html}</div>''')
    failed_steady = []
    for a in failed:  # 미수집 브랜드도 웹 판매신호는 노출
        for h in (steady.get(a["brand"]) or {}).get("hits") or []:
            failed_steady.append(
                f'<div><span class="k">{E(a["brand"])}</span> '
                f'<a class="new" href="{E(h["url"])}" target="_blank" rel="noopener">'
                f'{E(h["title"][:50])} <span class="nd">{E(h["authority"])}</span></a></div>')
    return "\n".join(cards), "\n".join(failed_steady)


def _naver_blocks(naver, ok, evidence):
    """§5 NAVER 수요 블록들. (cat_block, item_block, brand_block, brand_nodata, dom_html)."""
    all_sigs = naver.get("signals", [])
    by_src = lambda *srcs: [s for s in all_sigs if s["source"] in srcs]
    cat_block = _sig_rows(by_src("search_trend", "shopping_category", "shopping_keyword"))
    item_block = _sig_rows(by_src("item_search_trend"))
    sig_by_brand = {}  # 브랜드 수요 행에 실측 시그니처(주력·컬러) 병기 — §4와 조인
    for a in ok:
        top = ", ".join(n for n, _ in (a.get("items_top") or [])[:2])
        fam = (a.get("colors_family_top") or [["—"]])[0][0]
        sig_by_brand[a["brand"].lower()] = f"주력 {top} · {fam}" if top else ""
    brand_extra = {s["group"]: sig_by_brand.get(s["group"].lower(), "")
                   for s in by_src("brand_search_trend")}
    brand_block = _sig_rows(by_src("brand_search_trend"), extra=brand_extra)
    brand_nodata = _no_data_note(by_src("brand_search_trend"))
    domestic = [e for e in evidence if report._is_domestic_blog(e.get("url", ""))]
    dom_html = "".join(
        f'<li><a href="{E(e["url"])}" target="_blank" rel="noopener">'
        f'{E((e.get("title") or "")[:52] or _pubname(e["url"]))}</a> '
        f'<span class="nd">{E(_pubname(e["url"]))}</span></li>' for e in domestic)
    return cat_block, item_block, brand_block, brand_nodata, dom_html


def _appendix_blocks(demoted, ok, evidence, analysis, crawl):
    """§7 부록 블록들. (demo_block, detail_html, src_rows, tier_summary, lims, fail_html)."""
    demo_html = []
    for t in demoted:
        demo_html.append(f'''<div class="trend demo">
          <div class="trend-head">[{E(t.phase)}] <b>{E(t.name)}</b></div>
          <p>{E(t.rationale)}</p></div>''')
    demo_block = "\n".join(demo_html)

    detail_rows = []
    for a in ok:
        p = a.get("price")
        price = f"{a.get('currency','?')} {p['p50']} <span class='muted'>({p['min']}–{p['max']})</span>" if p else "—"
        detail_rows.append(f'''<tr><td><b>{E(a['brand'])}</b><br><span class="muted">{a['count']}개</span></td>
          <td>{price}<br><span class="muted">세일 {round(a['sale_ratio']*100)}%</span></td>
          <td>{E(", ".join(f"{n}·{c}" for n,c in (a.get('items_top') or [])[:4]))}</td>
          <td>{E(", ".join(f"{n}·{c}" for n,c in (a.get('colors_family_top') or [])[:4]))}</td>
          <td>{E(", ".join(f"{n}·{c}" for n,c in (a.get('silhouettes_top') or [])[:4]))}</td>
          <td>{E(", ".join(f"{n}·{c}" for n,c in (a.get('materials_top') or [])[:4]))}</td></tr>''')
    detail_html = "\n".join(detail_rows)

    src_rows = "\n".join(
        f'<tr class="tier{e.get("tier",4)}"><td>{E(e["id"])}</td><td>{E(e.get("authority","T4 저권위"))}</td>'
        f'<td><a href="{E(e["url"])}" target="_blank" rel="noopener" title="{E(e["url"])}">'
        f'{E((e.get("title") or "")[:56] or e["url"][:56])}</a></td>'
        f'<td>{E(_pubname(e["url"]))}</td>'
        f'<td>{E(e.get("brand") or "—")}</td></tr>' for e in evidence)

    tier_counts = Counter(e.get("authority", "T4 저권위") for e in evidence)
    tier_summary = " · ".join(f"{k} {v}" for k, v in sorted(tier_counts.items()))

    lims = "".join(f"<li>{E(l)}</li>" for l in analysis.limitations)
    fails = [r for r in crawl if not r["ok"]]
    fail_html = "".join(f"<li>{E(r['url'])} — {E(' '.join(r['error'].split()))}</li>" for r in fails[:8])
    return demo_block, detail_html, src_rows, tier_summary, lims, fail_html


def render_html(analysis, naver: dict, crawl_results: list[dict], evidence: list[dict],
                datalayer_aggregates: list[dict] | None = None,
                steady: dict | None = None) -> str:
    """render_report와 같은 입력 → 완결 HTML 문서 문자열 (섹션 빌더 조립)."""
    dl = datalayer_aggregates or []
    steady = steady or {}
    ev_urls = {e["id"]: e["url"] for e in evidence}
    ev_auth = {e["id"]: e.get("authority", "T4 저권위") for e in evidence}
    ev_title = {e["id"]: e.get("title") for e in evidence}

    backed = [t for t in analysis.trends if t.evidence_ids]
    demoted = [t for t in analysis.trends if not t.evidence_ids]
    ok = [a for a in dl if a.get("count")]
    failed = [a for a in dl if not a.get("count")]
    total = sum(a["count"] for a in ok)

    trend_block = _trend_section(backed, evidence, ev_urls, ev_auth, ev_title)
    ladder_html = _price_ladder(ok)
    cards_html, failed_steady_html = _brand_cards(ok, failed, steady)
    cat_block, item_block, brand_block, brand_nodata, dom_html = _naver_blocks(naver, ok, evidence)
    demo_block, detail_html, src_rows, tier_summary, lims, fail_html = _appendix_blocks(
        demoted, ok, evidence, analysis, crawl_results)

    item_bars = _bars(_roll(ok, "items_top"))
    color_bars = _bars(_roll(ok, "colors_family_top"), swatch=True)
    sil_bars = _bars(_roll(ok, "silhouettes_top"))
    mat_bars = _bars(_roll(ok, "materials_top"))
    top_item = _roll(ok, "items_top")[0][0]
    top_fam = _roll(ok, "colors_family_top")[0][0]
    top_sil = _roll(ok, "silhouettes_top")[0][0]
    top_mat = _roll(ok, "materials_top")[0][0]

    gaps_html = "".join(f"<li>{E(g)}</li>" for g in analysis.gaps)
    act_html = "".join(f"<li><b>{E(a.recommendation)}</b><br><span class='muted'>{E(a.rationale)}</span></li>"
                       for a in analysis.actions)

    HTML = f'''<title>캐시미어·니트웨어 MD 트렌드 리포트</title>
    <style>{_CSS}    </style>

    <div class="wrap">
    <header>
      <p class="eyebrow">MD Decision Report · Cashmere Knitwear</p>
      <h1>캐시미어·니트웨어 트렌드 리포트</h1>
      <div class="meta">
        <span>생성 <b>{date.today().isoformat()}</b></span>
        <span>벤치마크 <b>{len(ok)}</b>개 몰</span>
        <span>실측 상품 <b>{total:,}</b>개</span>
        <span>타깃 <b>{E(config.ANALYSIS['target'])}</b></span>
      </div>
    </header>

    <section>
      <h2 data-n="01">한 장 요약</h2>
      <div class="summary">
        <div class="row"><span class="tag">핵심 트렌드</span><span>{('[' + backed[0].phase + '] ' + E(backed[0].name)) if backed else '권위 매체 보도 기반 트렌드 없음'}</span></div>
        {"".join(f'<div class="row"><span class="tag">MD 액션</span><span>{E(a.recommendation)}</span></div>' for a in analysis.actions[:3])}
      </div>
    </section>

    <section>
      <h2 data-n="02">트렌드 · 권위 근거 T1·T2</h2>
      <p class="note">업계지(T1)·에디토리얼(T2) 보도를 근거로 묶은 시즌 테마. 보도 근거가 없는 관찰은 부록에 있다.</p>
      {trend_block}
    </section>

    <section>
      <h2 data-n="03">시장 실측 스냅샷</h2>
      <p class="lead">실측 {total:,}개 상품 최다 — 아이템 <b>{E(top_item)}</b> · 컬러 <b>{E(top_fam)}</b> · 실루엣 <b>{E(top_sil)}</b> · 소재 <b>{E(top_mat)}</b>.</p>
      <div class="grp">아이템</div><div class="bars">{item_bars}</div>
      <div class="grp">컬러 계열</div><div class="bars">{color_bars}</div>
      <div class="grp">실루엣</div><div class="bars">{sil_bars}</div>
      <div class="grp">소재</div><div class="bars">{mat_bars}</div>
      <div class="grp">가격 포지셔닝 · 중앙값(통화 상이)</div>
      <div class="ladder">{ladder_html}</div>
    </section>

    <section>
      <h2 data-n="04">브랜드 시그니처</h2>
      <p class="note">브랜드별 주력 아이템·컬러·가격·신상 흐름. 세일률 <span class="flag-hot">20% 이상</span>은 재고 압박, 최근 8주 신상 0은 업데이트 정체로 읽는다.</p>
      <div class="cards">{cards_html}</div>
      {f'<div class="missing">{failed_steady_html}</div>' if failed_steady_html else ''}
    </section>

    <section>
      <h2 data-n="05">국내 수요 · NAVER 데이터랩</h2>
      <p class="note">ratio는 요청별 최대=100 상대값(요청 간 절대 비교 금지). 스파크라인 = 최근 8주 주간 추이,
        ○=최고점 ●=최근. 검색 수요는 일부 20~39세(coverage mismatch).</p>
      <div class="grp">카테고리 수요</div>
      {cat_block or '<p class="muted">NAVER 신호 없음</p>'}
      {f'<div class="grp">아이템 수요 · 시그니처/유사 상품</div>{item_block}' if item_block else ''}
      {f'<div class="grp">벤치마크 브랜드 검색 수요 <span class="muted">— 실측 시그니처 병기</span></div>{brand_block}{brand_nodata}' if brand_block else ''}
      <div class="dom"><span class="dom-label">국내 블로그·커뮤니티 (참고용)</span>
        <ul class="dom">{dom_html}</ul></div>
    </section>

    <section>
      <h2 data-n="06">상품 공백 &amp; MD 액션</h2>
      <div class="grp">공백</div><ul class="gaps">{gaps_html}</ul>
      <div class="grp">추천 액션</div><ul class="acts">{act_html}</ul>
    </section>

    <section>
      <h2 data-n="07">부록</h2>
      <div class="grp">미검증 관찰</div>
      <p class="note">T1·T2 매체 보도가 없어 본문에서 제외한 관찰이다.</p>
      {demo_block}
      <details><summary>▸ 브랜드 상세 실측 (datalayer, Shopify 직수집)</summary>
        <div class="tbl-wrap"><table>
          <tr><th>브랜드</th><th>가격</th><th>아이템</th><th>컬러계열</th><th>실루엣</th><th>소재</th></tr>
          {detail_html}
        </table></div></details>
      <details><summary>▸ 출처 · 권위 티어 ({E(tier_summary)})</summary>
        <div class="tbl-wrap"><table>
          <tr><th>ID</th><th>권위</th><th>제목</th><th>매체</th><th>브랜드</th></tr>
          {src_rows}
        </table></div></details>
      <div class="grp">데이터 한계 · 수집 실패</div>
      <ul class="gaps">{lims}{fail_html}</ul>
    </section>

    <footer>md-trend-agent · 실측 데이터 = 벤치마크 공식몰 직수집</footer>
    </div>'''

    return ('<!doctype html><html><head><meta charset="utf-8"></head><body>'
            + HTML + '</body></html>')


if __name__ == "__main__":
    import json
    from poc.analyze import AnalysisOutput, _sanitize
    from poc import collect
    OUT = config.OUT_DIR
    crawl = json.loads((OUT / "crawl_results.json").read_text(encoding="utf-8"))
    naver = json.loads((OUT / "naver_raw.json").read_text(encoding="utf-8"))
    dl = json.loads((OUT / "datalayer_aggregates.json").read_text(encoding="utf-8"))
    analysis = AnalysisOutput(**json.loads((OUT / "analysis.json").read_text(encoding="utf-8")))
    steady = (json.loads((OUT / "steady_cache.json").read_text(encoding="utf-8"))
              if (OUT / "steady_cache.json").exists() else {})
    evidence = collect.build_evidence(crawl)
    analysis = _sanitize(analysis, evidence)
    html_doc = render_html(analysis, naver, crawl, evidence,
                           datalayer_aggregates=dl, steady=steady)
    path = OUT / "report.html"
    path.write_text(html_doc, encoding="utf-8")
    print(f"HTML 저장: {path} ({len(html_doc):,}자)")
