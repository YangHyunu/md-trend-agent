from pathlib import Path

from poc.rss import parse_feed, filter_by_terms

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
