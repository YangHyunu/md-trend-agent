"""스테디셀러/시그니처 신호 웹수집 (주1회 캐시).

판매량/랭킹 데이터가 없으므로 "bestseller·iconic·signature" 웹 언급을 신호로 쓴다.
권위 필터: T1·T2(에디토리얼 판정) + 해당 브랜드 공식(T3 signature 페이지)만.
T4 저권위는 버림 — 트렌드 근거 정책(MDA-10)과 동일 기준.
추출/해석 없음: 링크+제목 그대로 노출, 판단은 MD가.
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from poc import config
from poc.collect import _brand_for, classify_authority

MAX_AGE_DAYS = 7          # 주1회 — 이내면 재검색 스킵
MAX_HITS_PER_BRAND = 3    # 카드 노출 상한
_SIGNAL_WORDS = ("bestseller", "best seller", "best-selling", "bestselling",
                 "iconic", "signature", "cult", "hero piece", "hero product")


def steady_query(brand_name: str) -> str:
    return f'"{brand_name}" cashmere knitwear bestseller OR signature OR iconic'


def _mentions_signal(title: str, content: str) -> bool:
    blob = f"{title} {content}".lower()
    return any(w in blob for w in _SIGNAL_WORDS)


def filter_hits(results: list[dict], brand_name: str) -> list[dict]:
    """Tavily 결과 → 권위 통과분만. T1·T2 전부, T3는 해당 브랜드 공식몰만.

    브랜드명이 title/content에 없으면 배제 — 검색이 끌어온 남의 브랜드 결과 차단.
    """
    hits = []
    for r in results:
        url, title = r.get("url", ""), r.get("title", "")
        if not url or not _mentions_signal(title, r.get("content", "")):
            continue
        if brand_name.lower() not in f"{title} {r.get('content', '')}".lower():
            continue  # 예: '&Daughter' 쿼리에 Benetton 결과
        tier, authority = classify_authority(url, _brand_for(url))
        if tier > 3:
            # 커머스지 화이트리스트: 판매신호 근거로만 인정 (트렌드 근거는 여전히 T4)
            host = urlparse(url).netloc.lower()
            if not any(host == d or host.endswith("." + d) for d in config.STEADY_SOURCES):
                continue
            authority = "커머스지"
        elif tier == 3 and (_brand_for(url) or "").lower() != brand_name.lower():
            continue  # 남의 브랜드 공식몰은 이 브랜드의 시그니처 근거 아님
        hits.append({"url": url, "title": title, "tier": tier, "authority": authority})
        if len(hits) >= MAX_HITS_PER_BRAND:
            break
    return hits


def _is_fresh(entry: dict, as_of: date) -> bool:
    fetched = entry.get("fetched_at")
    if not fetched:
        return False
    return fetched >= (as_of - timedelta(days=MAX_AGE_DAYS)).isoformat()


def load_cache(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def fetch_steady(brands, cache_path: str | Path, *, as_of: date | None = None,
                 search_fn=None) -> dict:
    """브랜드별 시그니처 신호 수집. 캐시 7일 이내면 스킵 (주1회).

    search_fn(query)->list[dict]: 테스트 주입용. 기본은 Tavily.
    반환/캐시 형태: {brand: {"fetched_at": iso, "hits": [{url,title,tier,authority}]}}
    """
    as_of = as_of or date.today()
    cache = load_cache(cache_path)
    if search_fn is None:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        search_fn = lambda q: client.search(q, max_results=5).get("results", [])

    for b in brands:
        if not b.auto_collect:
            continue
        entry = cache.get(b.name)
        if entry and _is_fresh(entry, as_of):
            continue  # 주1회 — 신선하면 재검색 안 함
        try:
            results = search_fn(steady_query(b.name))
        except Exception as e:
            print(f" steady FAIL {b.name}: {type(e).__name__}", file=sys.stderr)
            continue  # 실패 시 기존 캐시 유지 (없으면 미수집)
        cache[b.name] = {"fetched_at": as_of.isoformat(),
                         "hits": filter_hits(results, b.name)}

    Path(cache_path).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def _offline_check() -> None:
    from types import SimpleNamespace as NS
    # filter: T2 에디토리얼 통과, T4 블로그 탈락, 신호어 없으면 탈락
    results = [
        {"url": "https://www.vogue.co.uk/article/x", "title": "Lisa Yang's iconic knit",
         "content": "the signature sweater"},
        {"url": "https://m.blog.naver.com/x/1", "title": "Lisa Yang bestseller haul", "content": ""},
        {"url": "https://www.wwd.com/y", "title": "Lisa Yang market report", "content": "no signal here"},
        {"url": "https://www.wwd.com/z", "title": "Benetton iconic cashmere", "content": ""},
    ]
    hits = filter_hits(results, "Lisa Yang")
    assert len(hits) == 1 and hits[0]["tier"] == 2, hits  # T4탈락·무신호탈락·타브랜드탈락
    # 커머스지 화이트리스트: T4지만 판매신호 근거로 통과, 라벨 '커머스지'
    commerce = [{"url": "https://www.realsimple.com/quince-sweater",
                 "title": "This Best-Selling Quince Cashmere Sweater", "content": ""},
                {"url": "https://someblog.com/quince", "title": "Quince bestseller", "content": ""}]
    ch = filter_hits(commerce, "Quince")
    assert len(ch) == 1 and ch[0]["authority"] == "커머스지", ch  # 비화이트리스트 T4는 탈락
    # T3: 본인 브랜드 공식몰만 통과
    own = [{"url": "https://us.lisa-yang.com/pages/bestsellers",
            "title": "Lisa Yang Bestsellers", "content": ""}]
    other = [{"url": "https://www.arch4.co.uk/pages/bestsellers",
              "title": "Lisa Yang style bestsellers", "content": ""}]  # 남의 T3몰
    assert len(filter_hits(own, "Lisa Yang")) == 1
    assert filter_hits(other, "Lisa Yang") == []
    # 캐시 신선도: 7일 이내 스킵(재검색 0회), 지나면 재검색
    calls = []
    fake = lambda q: (calls.append(q), [])[1]
    brands = [NS(name="Lisa Yang", auto_collect=True), NS(name="PLUSH'MERE", auto_collect=False)]
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "steady_cache.json"
        fetch_steady(brands, p, as_of=date(2026, 7, 21), search_fn=fake)
        assert len(calls) == 1  # auto_collect=False 제외
        fetch_steady(brands, p, as_of=date(2026, 7, 24), search_fn=fake)
        assert len(calls) == 1, "7일 이내인데 재검색함"
        fetch_steady(brands, p, as_of=date(2026, 7, 29), search_fn=fake)
        assert len(calls) == 2, "7일 지났는데 스킵함"
        # 실패 시 기존 캐시 유지
        def boom(q):
            raise RuntimeError("net down")
        cache = fetch_steady(brands, p, as_of=date(2026, 8, 10), search_fn=boom)
        assert cache["Lisa Yang"]["fetched_at"] == "2026-07-29", "실패가 캐시를 덮어씀"
    print("steady offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
    else:
        config.OUT_DIR.mkdir(exist_ok=True)
        cache = fetch_steady(config.BRANDS, config.OUT_DIR / "steady_cache.json")
        for name, e in cache.items():
            print(f"{name}: {len(e['hits'])}건 ({e['fetched_at']})")
            for h in e["hits"]:
                print(f"  [{h['authority']}] {h['title'][:60]} {h['url'][:70]}")
