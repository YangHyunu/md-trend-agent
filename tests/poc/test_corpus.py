from datetime import datetime, timezone

from poc.corpus import build_corpus_input

_NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _article(url: str, fetched: str) -> dict:
    return {
        "id": "a" + url[-8:],
        "source": "wwd:cashmere",
        "url": url,
        "title": "Cashmere Prices Climb",
        "published_at": "2026-07-20T09:00:00+00:00",
        "fetched_at": fetched,
        "matched_terms": ["cashmere"],
        "excerpt": "supply tightened",
    }


def test_build_corpus_input_windows_articles_and_collects_refs():
    articles = [
        _article("https://x/fresh-01", "2026-07-22T00:00:00+00:00"),
        _article("https://x/stale-01", "2026-07-01T00:00:00+00:00"),
    ]
    crawl = [{"query": "니트 트렌드", "title": "올가을 니트", "url": "https://blog/1",
              "content": "x" * 500}]
    prior = [{"label_ko": "포인텔 니트", "label_en": "pointelle knit",
              "category": "소재", "aliases": [], "naver_queries": ["포인텔"],
              "source_refs": ["a-old"], "rationale": "지난주"}]

    bundle, valid_refs = build_corpus_input(articles, crawl, prior, now=_NOW)

    assert [a["ref"] for a in bundle["articles"]] == ["afresh-01"]
    assert bundle["websearch"][0]["ref"] == "w0"
    assert len(bundle["websearch"][0]["content"]) == 300
    assert bundle["prior_concepts"] == [
        {"label_ko": "포인텔 니트", "label_en": "pointelle knit", "category": "소재"}
    ]
    assert valid_refs == {"afresh-01", "w0"}
