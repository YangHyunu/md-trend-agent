"""Tavily 웹 검색 + Crawl4AI 수집 + evidence 생성."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from poc import config

EXCERPT_CHARS = 3000   # evidence 발췌 길이 (원문 전체 재배포 금지)
MIN_TEXT_CHARS = 500   # 이하면 추출 실패 판정 (SPEC Content Collector 기준)
STORE_TEXT_CHARS = 20000


def _canonical(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}"


def discover_urls() -> list[dict]:
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    found, seen = [], set()
    for q in config.TAVILY_QUERIES[: config.MAX_TAVILY_QUERIES]:
        try:
            resp = client.search(q, max_results=5)
        except Exception as e:
            print(f" tavily FAIL {q!r}: {e}", file=sys.stderr)
            continue
        for r in resp.get("results", []):
            u = r.get("url", "")
            if not u.startswith(("http://", "https://")):
                continue
            c = _canonical(u)
            if c in seen:
                continue
            seen.add(c)
            found.append({"url": u, "found_via": q})
    return found


def _brand_for(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for b in config.BRANDS:
        if not b.auto_collect:
            continue
        if urlparse(b.url).netloc.lower() in host or host in urlparse(b.url).netloc.lower():
            return b.name
    return None


def select_urls(discovered: list[dict]) -> list[str]:
    """공식몰 우선 + 발견 URL, 총 MAX_CRAWL_URLS, 도메인당 MAX_PER_DOMAIN."""
    urls: list[str] = [b.url for b in config.BRANDS if b.auto_collect]
    per_domain: dict[str, int] = {}
    for u in urls:
        d = urlparse(u).netloc.lower()
        per_domain[d] = per_domain.get(d, 0) + 1
    for item in discovered:
        if len(urls) >= config.MAX_CRAWL_URLS:
            break
        u = item["url"]
        d = urlparse(u).netloc.lower()
        if per_domain.get(d, 0) >= config.MAX_PER_DOMAIN:
            continue
        if _canonical(u) in {_canonical(x) for x in urls}:
            continue
        urls.append(u)
        per_domain[d] = per_domain.get(d, 0) + 1
    return urls[: config.MAX_CRAWL_URLS]


async def _crawl_async(urls: list[str]) -> list[dict]:
    from crawl4ai import AsyncWebCrawler
    results = []
    async with AsyncWebCrawler() as crawler:
        for u in urls:
            fetched_at = datetime.now(timezone.utc).isoformat()
            try:
                r = await asyncio.wait_for(
                    crawler.arun(url=u), timeout=config.CRAWL_TIMEOUT_SEC)
                text = str(r.markdown or "") if r.success else ""
                ok = len(text) >= MIN_TEXT_CHARS
                results.append({
                    "url": u, "ok": ok, "text": text[:STORE_TEXT_CHARS],
                    "error": None if ok else f"추출 실패: 본문 {len(text)}자 (<{MIN_TEXT_CHARS})",
                    "fetched_at": fetched_at,
                })
            except Exception as e:
                results.append({"url": u, "ok": False, "text": "",
                                "error": f"{type(e).__name__}: {e}", "fetched_at": fetched_at})
            print(f" crawl {'OK ' if results[-1]['ok'] else 'FAIL'} {u}", file=sys.stderr)
    return results


def crawl_urls(urls: list[str]) -> list[dict]:
    return asyncio.run(_crawl_async(urls))


def build_evidence(crawl_results: list[dict]) -> list[dict]:
    evidence = []
    for r in crawl_results:
        if not r["ok"]:
            continue
        brand = _brand_for(r["url"])
        evidence.append({
            "id": f"E{len(evidence) + 1:03d}",
            "url": r["url"],
            "excerpt": r["text"][:EXCERPT_CHARS],
            "brand": brand,
            "source_type": "official" if brand else "web",
            "fetched_at": r["fetched_at"],
        })
    return evidence


def collect() -> tuple[list[dict], list[dict]]:
    discovered = discover_urls()
    urls = select_urls(discovered)
    results = crawl_urls(urls)
    return results, build_evidence(results)


def _offline_check() -> None:
    assert _canonical("https://Example.com/a/?x=1") == "https://example.com/a"
    assert _brand_for("https://www.quince.com/women/cashmere/x") == "Quince"
    assert _brand_for("https://blog.naver.com/foo") is None
    urls = select_urls([{"url": f"https://site{i}.com/p", "found_via": "q"} for i in range(30)])
    assert len(urls) <= config.MAX_CRAWL_URLS
    fake = [{"url": "https://www.quince.com/w", "ok": True, "text": "x" * 600,
             "error": None, "fetched_at": "t"},
            {"url": "https://a.com", "ok": False, "text": "", "error": "e", "fetched_at": "t"}]
    ev = build_evidence(fake)
    assert len(ev) == 1 and ev[0]["id"] == "E001" and ev[0]["source_type"] == "official"
    print("collect offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
    else:
        limit = 3 if "--limit3" in sys.argv else None
        config.OUT_DIR.mkdir(exist_ok=True)
        if limit:
            urls = [b.url for b in config.BRANDS if b.auto_collect][:limit]
            results = crawl_urls(urls)
            evidence = build_evidence(results)
        else:
            results, evidence = collect()
        (config.OUT_DIR / "crawl_results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        (config.OUT_DIR / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = sum(r["ok"] for r in results)
        print(f"crawled ok={ok}/{len(results)} evidence={len(evidence)}")
