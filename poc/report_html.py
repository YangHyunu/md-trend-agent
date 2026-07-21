"""HTML 보고서 렌더러 — 코드가 렌더링, LLM 자유 생성 금지 (report.py의 HTML 짝).

이미지(신상 썸네일·기사 og:image)는 외부 URL <img> — 로컬 파일/일반 호스팅에서 보임.
report.py와 동일 데이터·동일 게이팅(backed/demoted) 소비. 스타일은 MD 대시보드-닥.
"""
import html as _html
import sys
from collections import Counter
from datetime import date

from poc import config, report

FAM_COLOR = {  # 8계열 시맨틱 스와치
    "뉴트럴": "#8b8b8f", "베이지·브라운": "#b08d5a", "블루·네이비": "#3a5a8a",
    "그린": "#5e8a5e", "레드·핑크": "#c06a7e", "옐로·오렌지": "#d1a24a",
    "퍼플": "#8a6aa8", "멀티·패턴": "linear-gradient(90deg,#c06a7e,#d1a24a,#5e8a5e,#3a5a8a)",
}
E = lambda s: _html.escape(str(s))


def render_html(analysis, naver: dict, crawl_results: list[dict], evidence: list[dict],
                datalayer_aggregates: list[dict] | None = None,
                steady: dict | None = None) -> str:
    """render_report와 같은 입력 → 완결 HTML 문서 문자열."""
    crawl = crawl_results
    dl = datalayer_aggregates or []
    steady = steady or {}
    ev_urls = {e["id"]: e["url"] for e in evidence}
    ev_auth = {e["id"]: e.get("authority", "T4 저권위") for e in evidence}

    backed = [t for t in analysis.trends if t.evidence_ids]
    demoted = [t for t in analysis.trends if not t.evidence_ids]
    ok = [a for a in dl if a.get("count")]
    failed = [a for a in dl if not a.get("count")]
    total = sum(a["count"] for a in ok)


    def roll(key):
        c = Counter()
        for a in ok:
            for n, cnt in (a.get(key) or []):
                c[n] += cnt
        return c.most_common()


    def cross(t):
        return report._trend_crosscheck(f"{t.name} {t.rationale}", dl).replace("  - 실측 대조: ", "")


    def bars(pairs, topn=8, swatch=False):
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


    def evlink(ids):
        return " ".join(
            f'<a class="ev" href="{E(ev_urls.get(i, "#"))}" target="_blank" rel="noopener">'
            f'{E(i)} <em>{E(ev_auth.get(i, ""))}</em></a>' for i in ids)


    # ── §2 트렌드 ──
    trend_html = []
    for phase in ("상승", "주류", "포화", "둔화"):
        items = [t for t in backed if t.phase == phase]
        if not items:
            continue
        trend_html.append(f'<h3 class="phase phase-{phase}">{E(phase)}</h3>')
        for t in items:
            ev_imgs = [e for e in evidence
                       if e["id"] in t.evidence_ids and e.get("image")][:2]
            img_html = "".join(
                f'<a href="{E(e["url"])}" target="_blank" rel="noopener" class="thumb">'
                f'<img src="{E(e["image"])}" alt="{E(e["id"])}" loading="lazy"></a>' for e in ev_imgs)
            trend_html.append(f'''<div class="trend">
              <div class="trend-head"><b>{E(t.name)}</b> {evlink(t.evidence_ids)}</div>
              <p>{E(t.rationale)}</p>
              {f'<div class="thumbs">{img_html}</div>' if img_html else ''}
              <div class="xcheck"><span class="xtag">실측 대조</span>{E(cross(t))}</div></div>''')
    trend_block = "\n".join(trend_html) or '<p class="muted">권위 근거(T1·T2) 트렌드 0건 — §3 실측으로 판단.</p>'

    # ── §3 가격 사다리 ──
    ladder = sorted(((a["brand"], a["price"]["p50"], a.get("currency") or "?")
                     for a in ok if a.get("price")), key=lambda x: x[1])
    lad_span = (ladder[-1][1] - ladder[0][1]) if ladder else 0  # 1개 브랜드면 0 → 좌측 고정
    lad_min = ladder[0][1] if ladder else 0
    ladder_html = "".join(
        f'<div class="lad"><span class="lad-b">{E(b)}</span>'
        f'<span class="lad-bar" style="left:{((p - lad_min) / lad_span * 100) if lad_span else 0:.0f}%"></span>'
        f'<span class="lad-p">{E(cur)}{p:.0f}</span></div>' for b, p, cur in ladder)

    # ── §4 브랜드 시그니처 ──
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
    cards_html = "\n".join(cards)
    failed_html = " · ".join(E(a['brand']) for a in failed)
    failed_steady = []
    for a in failed:  # 미수집 브랜드도 웹 판매신호는 노출
        for h in (steady.get(a["brand"]) or {}).get("hits") or []:
            failed_steady.append(
                f'<div><span class="k">{E(a["brand"])}</span> '
                f'<a class="new" href="{E(h["url"])}" target="_blank" rel="noopener">'
                f'{E(h["title"][:50])} <span class="nd">{E(h["authority"])}</span></a></div>')
    failed_steady_html = "\n".join(failed_steady)

    # ── §5 NAVER ──
    naver_html = []
    for s in naver.get("signals", []):
        ser = s["series"]
        if not ser:
            continue
        latest, peak = ser[-1], max(ser, key=lambda d: d["ratio"])
        naver_html.append(f'<li><b>{E(s["group"])}</b> ({E(s["observed_segment"])}세) — '
                          f'최근 {E(latest["period"])} ratio {latest["ratio"]}, 최고 {peak["ratio"]}</li>')
    naver_block = "".join(naver_html) or '<li class="muted">NAVER 신호 없음</li>'
    domestic = [e for e in evidence if report._is_domestic_blog(e.get("url", ""))]
    dom_html = "".join(f'<li><a href="{E(e["url"])}" target="_blank" rel="noopener">{E(e["id"])}</a></li>'
                       for e in domestic)

    # ── §6 갭·액션 ──
    gaps_html = "".join(f"<li>{E(g)}</li>" for g in analysis.gaps)
    act_html = "".join(f"<li><b>{E(a.recommendation)}</b><br><span class='muted'>{E(a.rationale)}</span></li>"
                       for a in analysis.actions)

    # ── §7 부록 ──
    demo_html = []
    for t in demoted:
        demo_html.append(f'''<div class="trend demo">
          <div class="trend-head">[{E(t.phase)}] <b>{E(t.name)}</b></div>
          <p>{E(t.rationale)}</p>
          <div class="xcheck"><span class="xtag">실측 대조</span>{E(cross(t))}</div></div>''')
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
        f'<td><a href="{E(e["url"])}" target="_blank" rel="noopener">{E(e["url"][:60])}</a></td>'
        f'<td>{E(e.get("brand") or "—")}</td></tr>' for e in evidence)

    tier_counts = Counter(e.get("authority", "T4 저권위") for e in evidence)
    tier_summary = " · ".join(f"{k} {v}" for k, v in sorted(tier_counts.items()))

    lims = "".join(f"<li>{E(l)}</li>" for l in analysis.limitations)
    fails = [r for r in crawl if not r["ok"]]
    fail_html = "".join(f"<li>{E(r['url'])} — {E(' '.join(r['error'].split()))}</li>" for r in fails[:8])

    top_item = roll("items_top")[0][0]
    top_fam = roll("colors_family_top")[0][0]
    top_sil = roll("silhouettes_top")[0][0]
    top_mat = roll("materials_top")[0][0]

    HTML = f'''<title>캐시미어·니트웨어 MD 트렌드 리포트</title>
    <style>
    :root {{
      --paper:#f5f6f7; --ink:#1a1d21; --muted:#6b7076; --line:#e2e4e7; --card:#ffffff;
      --accent:#34506b; --accent-soft:#e8edf2; --hot:#c0492f; --warn:#b8862a;
      --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
      --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    }}
    @media (prefers-color-scheme:dark) {{
      :root {{ --paper:#16181b; --ink:#e8eaed; --muted:#9aa0a6; --line:#2b2f34; --card:#1e2125;
        --accent:#7ba3c8; --accent-soft:#233240; --hot:#e07a5f; --warn:#d6a94a; }}
    }}
    :root[data-theme="dark"] {{ --paper:#16181b; --ink:#e8eaed; --muted:#9aa0a6; --line:#2b2f34; --card:#1e2125;
      --accent:#7ba3c8; --accent-soft:#233240; --hot:#e07a5f; --warn:#d6a94a; }}
    :root[data-theme="light"] {{ --paper:#f5f6f7; --ink:#1a1d21; --muted:#6b7076; --line:#e2e4e7; --card:#ffffff;
      --accent:#34506b; --accent-soft:#e8edf2; --hot:#c0492f; --warn:#b8862a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans);
      line-height:1.55; -webkit-font-smoothing:antialiased; }}
    .wrap {{ max-width:820px; margin:0 auto; padding:48px 24px 96px; }}
    header {{ border-bottom:2px solid var(--ink); padding-bottom:20px; margin-bottom:8px; }}
    .eyebrow {{ font-family:var(--mono); font-size:11px; letter-spacing:.18em; text-transform:uppercase;
      color:var(--accent); margin:0 0 10px; }}
    h1 {{ font-family:var(--serif); font-size:34px; line-height:1.15; margin:0 0 12px; text-wrap:balance; font-weight:600; }}
    .meta {{ font-family:var(--mono); font-size:12.5px; color:var(--muted); display:flex; gap:18px; flex-wrap:wrap; }}
    .meta b {{ color:var(--ink); font-variant-numeric:tabular-nums; }}
    section {{ margin-top:44px; }}
    h2 {{ font-family:var(--serif); font-size:13px; letter-spacing:.05em; text-transform:uppercase;
      color:var(--muted); font-weight:600; margin:0 0 4px; display:flex; align-items:baseline; gap:10px; }}
    h2::before {{ content:attr(data-n); font-family:var(--mono); color:var(--accent); font-size:12px; }}
    .lead {{ font-family:var(--serif); font-size:19px; line-height:1.4; margin:6px 0 20px; text-wrap:pretty; }}
    .note {{ font-size:12.5px; color:var(--muted); margin:0 0 16px; }}
    /* §1 summary */
    .summary {{ background:var(--card); border:1px solid var(--line); border-radius:4px; padding:22px 24px; }}
    .summary .row {{ display:flex; gap:12px; padding:9px 0; border-bottom:1px solid var(--line); }}
    .summary .row:last-child {{ border:0; }}
    .summary .tag {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase;
      color:var(--accent); min-width:74px; padding-top:2px; }}
    /* bars */
    .bars {{ display:flex; flex-direction:column; gap:7px; margin:14px 0 4px; }}
    .bar-row {{ display:grid; grid-template-columns:120px 1fr 40px; align-items:center; gap:12px; font-size:13px; }}
    .bar-label {{ color:var(--ink); }}
    .bar-track {{ height:9px; background:var(--accent-soft); border-radius:5px; overflow:hidden; }}
    .bar-fill {{ display:block; height:100%; border-radius:5px; }}
    .bar-pct {{ font-family:var(--mono); font-size:12px; color:var(--muted); text-align:right; font-variant-numeric:tabular-nums; }}
    .axis {{ font-family:var(--mono); font-size:12.5px; color:var(--muted); margin:18px 0 6px; letter-spacing:.02em; }}
    .axis b {{ color:var(--accent); }}
    .grp {{ font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:.1em;
      color:var(--muted); margin:20px 0 8px; }}
    /* price ladder */
    .ladder {{ position:relative; margin:20px 0 8px; display:flex; flex-direction:column; gap:3px; }}
    .lad {{ position:relative; height:24px; display:flex; align-items:center; }}
    .lad-b {{ width:130px; font-size:12.5px; }}
    .lad-bar {{ position:absolute; width:9px; height:9px; border-radius:50%; background:var(--accent);
      margin-left:130px; transform:translateX(-4px); }}
    .lad-p {{ position:absolute; right:0; font-family:var(--mono); font-size:12px; color:var(--muted);
      font-variant-numeric:tabular-nums; }}
    /* §4 cards */
    .cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; margin-top:14px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:4px; padding:15px 16px; }}
    .card-top {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:9px; }}
    .card-top b {{ font-size:15px; font-family:var(--serif); }}
    .count {{ font-family:var(--mono); font-size:11.5px; color:var(--muted); }}
    .sig {{ font-size:12.5px; color:var(--ink); margin-bottom:10px; }}
    .chip {{ display:inline-block; font-size:11px; padding:1px 8px; border:1px solid; border-radius:20px;
      margin-right:6px; }}
    .k {{ font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
    .stats {{ display:flex; gap:14px; font-size:12.5px; font-variant-numeric:tabular-nums; flex-wrap:wrap; }}
    .stats b {{ font-family:var(--mono); }}
    .newest {{ margin-top:10px; padding-top:9px; border-top:1px solid var(--line); font-size:12px; }}
    .thumbs {{ display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }}
    .thumb {{ display:block; width:72px; text-decoration:none; }}
    .trend .thumb {{ width:120px; }}
    .thumb img {{ width:100%; aspect-ratio:3/4; object-fit:cover; border-radius:3px;
      border:1px solid var(--line); display:block; }}
    .th-cap {{ display:block; font-family:var(--mono); font-size:9.5px; color:var(--muted);
      margin-top:3px; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .new {{ text-decoration:none; color:var(--accent); }}
    .new:hover {{ text-decoration:underline; }}
    .nd {{ font-family:var(--mono); font-size:10.5px; color:var(--muted); }}
    .flag-hot {{ color:var(--hot); font-weight:600; }}
    .flag-warn {{ color:var(--warn); }}
    .missing {{ font-size:12.5px; color:var(--muted); margin-top:14px; padding-top:12px; border-top:1px dashed var(--line); }}
    /* trends */
    .phase {{ font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:.12em;
      margin:22px 0 10px; color:var(--accent); }}
    .trend {{ border-left:2px solid var(--accent); padding:2px 0 2px 16px; margin-bottom:16px; }}
    .trend.demo {{ border-left-color:var(--line); }}
    .trend-head b {{ font-size:15px; }}
    .trend p {{ margin:4px 0 8px; font-size:13.5px; color:var(--ink); }}
    .ev {{ font-family:var(--mono); font-size:10.5px; text-decoration:none; color:var(--accent);
      border:1px solid var(--accent-soft); padding:1px 5px; border-radius:3px; margin-left:4px; white-space:nowrap; }}
    .ev em {{ font-style:normal; color:var(--muted); }}
    .xcheck {{ font-size:12px; color:var(--muted); background:var(--accent-soft); padding:8px 12px; border-radius:4px; }}
    .xtag {{ font-family:var(--mono); font-size:9.5px; text-transform:uppercase; letter-spacing:.1em;
      color:var(--accent); margin-right:8px; }}
    /* lists */
    ul {{ padding-left:0; list-style:none; margin:0; }}
    .gaps li, .naver li {{ padding:6px 0 6px 18px; position:relative; font-size:13.5px; border-bottom:1px solid var(--line); }}
    .gaps li::before {{ content:"→"; position:absolute; left:0; color:var(--accent); }}
    .acts {{ counter-reset:a; }}
    .acts li {{ counter-increment:a; padding:10px 0 10px 30px; position:relative; border-bottom:1px solid var(--line); font-size:13.5px; }}
    .acts li::before {{ content:counter(a); position:absolute; left:0; top:10px; font-family:var(--mono);
      background:var(--accent); color:#fff; width:19px; height:19px; border-radius:50%; text-align:center;
      font-size:11px; line-height:19px; }}
    .muted {{ color:var(--muted); }}
    .dom {{ margin-top:14px; font-size:12.5px; }}
    .dom-label {{ font-family:var(--mono); font-size:10.5px; text-transform:uppercase; letter-spacing:.08em; color:var(--warn); }}
    .dom a {{ color:var(--muted); }}
    /* appendix */
    details {{ border:1px solid var(--line); border-radius:4px; margin-top:14px; }}
    summary {{ cursor:pointer; padding:12px 16px; font-family:var(--mono); font-size:12px; color:var(--accent); }}
    .tbl-wrap {{ overflow-x:auto; padding:0 16px 16px; }}
    table {{ border-collapse:collapse; width:100%; font-size:12px; }}
    th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
    th {{ font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
    td {{ font-variant-numeric:tabular-nums; }}
    tr.tier1 td:nth-child(2), tr.tier2 td:nth-child(2) {{ color:var(--accent); font-weight:600; }}
    tr.tier4 td:nth-child(2) {{ color:var(--muted); }}
    a:focus-visible, summary:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
    footer {{ margin-top:56px; padding-top:16px; border-top:1px solid var(--line);
      font-family:var(--mono); font-size:11px; color:var(--muted); }}
    </style>

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
        <div class="row"><span class="tag">뜨는 것</span><span>{('[' + backed[0].phase + '] ' + E(backed[0].name)) if backed else '권위 근거 트렌드 없음 — 시장 실측으로 판단'}</span></div>
        {"".join(f'<div class="row"><span class="tag">MD 액션</span><span>{E(a.recommendation)}</span></div>' for a in analysis.actions[:3])}
      </div>
    </section>

    <section>
      <h2 data-n="02">트렌드 · 권위 근거 T1·T2</h2>
      <p class="note">업계지·에디토리얼 근거가 있는 트렌드만. 근거 없는 관찰은 부록. 각 트렌드 아래 <b>실측 대조</b> = 벤치마크 몰의 실제 노출(코드 조인).</p>
      {trend_block}
    </section>

    <section>
      <h2 data-n="03">시장 실측 스냅샷</h2>
      <p class="lead">시장은 <b>{E(top_item)}</b> 중심, <b>{E(top_fam)}</b> 컬러와 <b>{E(top_sil)}</b> 실루엣이 지배하고 소재는 <b>{E(top_mat)}</b>가 압도한다.</p>
      <div class="grp">아이템</div><div class="bars">{bars(roll("items_top"))}</div>
      <div class="grp">컬러 계열</div><div class="bars">{bars(roll("colors_family_top"), swatch=True)}</div>
      <div class="grp">실루엣</div><div class="bars">{bars(roll("silhouettes_top"))}</div>
      <div class="grp">소재</div><div class="bars">{bars(roll("materials_top"))}</div>
      <div class="grp">가격 포지셔닝 · 중앙값(통화 상이)</div>
      <div class="ladder">{ladder_html}</div>
    </section>

    <section>
      <h2 data-n="04">브랜드 시그니처</h2>
      <p class="note">브랜드당 한 줄 — 주력·지배축·가격·신상. 세일률 <span class="flag-hot">20%↑</span>=재고압박 신호, 신상 0=업데이트 정체.</p>
      <div class="cards">{cards_html}</div>
      <p class="missing"><b>미수집</b> (소스 미구현 갭): {failed_html}</p>
      {f'<div class="missing">{failed_steady_html}</div>' if failed_steady_html else ''}
    </section>

    <section>
      <h2 data-n="05">국내 수요 · NAVER 데이터랩</h2>
      <p class="note">ratio는 요청별 최대=100 상대값. 25~39세를 정확히 못 잡아 20~39세(coverage mismatch).</p>
      <ul class="naver">{naver_block}</ul>
      <div class="dom"><span class="dom-label">국내 웹 참고 — 판단 근거 아님</span>
        <ul class="dom">{dom_html}</ul></div>
    </section>

    <section>
      <h2 data-n="06">상품 공백 &amp; MD 액션</h2>
      <div class="grp">공백</div><ul class="gaps">{gaps_html}</ul>
      <div class="grp">추천 액션</div><ul class="acts">{act_html}</ul>
    </section>

    <section>
      <h2 data-n="07">부록</h2>
      <div class="grp">미검증 관찰 · 권위 근거 없음</div>
      <p class="note">권위 매체(T1·T2) 근거가 없어 트렌드로 확정 못 함. 단 벤치마크 실측 대조는 유효.</p>
      {demo_block}
      <details><summary>▸ 브랜드 상세 실측 (datalayer, Shopify 직수집)</summary>
        <div class="tbl-wrap"><table>
          <tr><th>브랜드</th><th>가격</th><th>아이템</th><th>컬러계열</th><th>실루엣</th><th>소재</th></tr>
          {detail_html}
        </table></div></details>
      <details><summary>▸ 출처 · 권위 티어 ({E(tier_summary)})</summary>
        <div class="tbl-wrap"><table>
          <tr><th>ID</th><th>권위</th><th>URL</th><th>브랜드</th></tr>
          {src_rows}
        </table></div></details>
      <div class="grp">데이터 한계 · 수집 실패</div>
      <ul class="gaps">{lims}{fail_html}</ul>
    </section>

    <footer>md-trend-agent · 코드 렌더링(LLM 자유생성 아님) · 실측 = Shopify 직수집 datalayer</footer>
    </div>'''

    return ('<!doctype html><html><head><meta charset="utf-8"></head><body>'
            + HTML + '</body></html>')

def _offline_check() -> None:
    import json
    from poc.analyze import Action, AnalysisOutput, Trend
    analysis = AnalysisOutput(
        trends=[Trend(name="브러시드 캐시미어 소재 세분화", phase="상승",
                      rationale="에디토리얼 지목", evidence_ids=["E014"]),
                Trend(name="근거약한관찰", phase="둔화", rationale="정성", evidence_ids=[])],
        design_map=[], gaps=["컬러블록 부재"],
        actions=[Action(recommendation="뉴트럴 확대", rationale="지배축", evidence_ids=["E014"])],
        limitations=["표본 작음"])
    naver = {"signals": [{"source": "shopping_keyword", "group": "캐시미어니트",
                          "series": [{"period": "2026-06-01", "ratio": 100.0}],
                          "requested_segment": "25-39", "observed_segment": "20-39",
                          "coverage_mismatch": True, "note": ""}], "failures": []}
    crawl = [{"url": "https://x.com", "ok": False, "text": "", "error": "timeout", "fetched_at": "t"}]
    ev = [{"id": "E014", "url": "https://www.harpersbazaar.com/x", "brand": None, "tier": 2,
           "authority": "T2 에디토리얼", "image": "https://media.hb.com/hero.jpg",
           "fetched_at": "2026-07-20T00:00:00"}]
    dl = [{"brand": "Arch4", "source": "shopify", "count": 2, "failure": None,
           "currency": "GBP", "price": {"min": 130.0, "max": 240.0, "p25": 150.0,
                                        "p50": 185.0, "p75": 220.0, "n": 2},
           "sale_ratio": 0.5, "colors_top": [("Camel", 2)],
           "colors_family_top": [("뉴트럴", 2)], "silhouettes_top": [("Relaxed", 2)],
           "items_top": [("Sweater", 2)], "items_unmatched": 1,
           "materials_top": [("cashmere", 2)],
           "newness": {"weeks": 8, "recent_count": 1, "latest": "2026-07-01"},
           "newest": [{"url": "https://a.co/p/x", "item": "Sweater",
                       "published_at": "2026-07-01", "image_url": "https://cdn.a.co/x.jpg"}]},
          {"brand": "Quince", "source": None, "count": 0, "failure": "지원 소스 없음"}]
    steady = {"Quince": {"fetched_at": "2026-07-21", "hits": [
        {"url": "https://www.realsimple.com/q", "title": "Best-Selling Quince Cashmere",
         "tier": 4, "authority": "커머스지"}]}}
    out = render_html(analysis, naver, crawl, ev, datalayer_aggregates=dl, steady=steady)
    assert out.startswith("<!doctype html>") and out.endswith("</html>")
    assert '<img src="https://cdn.a.co/x.jpg"' in out, "신상 썸네일 누락"
    assert '<img src="https://media.hb.com/hero.jpg"' in out, "트렌드 og:image 누락"
    assert "근거약한관찰" in out and "미검증 관찰" in out, "강등 트렌드 부록 누락"
    assert "Best-Selling Quince Cashmere" in out, "미수집 브랜드 steady 신호 누락"
    assert "T2 에디토리얼" in out and "1,902" not in out
    assert out.count("<details>") >= 2, "부록 접기 누락"
    print("report_html offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
        raise SystemExit(0)
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
