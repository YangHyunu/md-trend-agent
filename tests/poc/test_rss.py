from pathlib import Path

import httpx

from poc import config
from poc.rss import parse_feed, filter_by_terms, fetch_all_feeds

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_feed_maps_items():
    xml = (FIXTURES / "wwd_cashmere_feed.xml").read_text()
    articles = parse_feed(xml, source="wwd:cashmere")
    assert len(articles) == 2
    first = articles[0]
    assert first["url"] == "https://wwd.com/fashion-news/cashmere-prices-climb/"
    assert first["title"] == "Cashmere Prices Climb as Supply Tightens"
    assert first["source"] == "wwd:cashmere"
    assert first["published_at"].startswith("2026-07-20")
    assert first["id"].startswith("a") and len(first["id"]) == 11
    assert "<p>" not in first["excerpt"]
    assert first["matched_terms"] == []


def test_parse_feed_skips_items_without_link():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>no link</title></item>
    </channel></rss>"""
    assert parse_feed(xml, source="wwd:wool") == []


def test_filter_by_terms_keeps_only_matches_and_records_terms():
    xml = (FIXTURES / "glossy_all_feed.xml").read_text()
    articles = parse_feed(xml, source="glossy:vogue")
    kept = filter_by_terms(articles, ["cashmere", "cardigan", "knit"])
    assert len(kept) == 1
    assert kept[0]["url"] == "https://www.vogue.com/article/cashmere-cardigans"
    assert sorted(kept[0]["matched_terms"]) == ["cardigan", "cashmere", "knit"]


def test_filter_by_terms_is_case_insensitive():
    articles = [{"title": "CASHMERE now", "excerpt": "", "matched_terms": []}]
    assert filter_by_terms(articles, ["cashmere"])[0]["matched_terms"] == ["cashmere"]


_WWD_XML = (FIXTURES / "wwd_cashmere_feed.xml").read_text()
_GLOSSY_XML = (FIXTURES / "glossy_all_feed.xml").read_text()


def _feed_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "wwd.com":
        if "cashmere" in request.url.path:
            return httpx.Response(200, text=_WWD_XML)
        return httpx.Response(404)
    return httpx.Response(200, text=_GLOSSY_XML)


def _feed_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_feed_handler))


def test_fetch_all_feeds_tags_wwd_and_filters_glossy():
    result = fetch_all_feeds(client=_feed_client())
    wwd = [a for a in result["articles"] if a["source"] == "wwd:cashmere"]
    glossy = [a for a in result["articles"] if a["source"].startswith("glossy:")]
    assert len(wwd) == 2
    assert all(a["matched_terms"] == ["cashmere"] for a in wwd)
    # 글로시 피드 3개 모두 같은 fixture(기사 2개 중 1개만 니트 매칭)를 반환
    assert len(glossy) == 3
    assert all("cashmere" in a["matched_terms"] for a in glossy)
    # knitwear/wool 태그피드는 404 → failures에 기록, 파이프라인은 진행
    assert "wwd:knitwear" in result["failures"]
    assert "wwd:wool" in result["failures"]
