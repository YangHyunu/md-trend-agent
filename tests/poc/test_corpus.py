from datetime import datetime, timezone

from poc.corpus import Concept, CorpusOutput, build_corpus_input, validate_concepts

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


def _concept(**over) -> Concept:
    base = dict(
        label_ko="포인텔 니트", label_en="pointelle knit", aliases=["pointelle"],
        category="소재", naver_queries=["포인텔", "pointelle"],
        source_refs=["afresh-01"], rationale="WWD 언급",
    )
    return Concept(**{**base, **over})


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


def test_validate_drops_unknown_refs_and_trims():
    out = CorpusOutput(concepts=[
        _concept(),
        _concept(label_ko="유령 개념", source_refs=["ghost-ref"]),
    ])
    kept, dropped = validate_concepts(out, {"afresh-01"})
    assert [c.label_ko for c in kept] == ["포인텔 니트"]
    assert kept[0].source_refs == ["afresh-01"]
    assert kept[0].naver_queries == ["포인텔"]  # 비한글 쿼리 제거
    assert dropped == [{"label_ko": "유령 개념", "reason": "no_valid_source_refs"}]


def test_validate_drops_concepts_without_korean_query():
    out = CorpusOutput(concepts=[_concept(naver_queries=["pointelle knit"])])
    kept, dropped = validate_concepts(out, {"afresh-01"})
    assert kept == []
    assert dropped[0]["reason"] == "no_korean_query"


def test_validate_caps_at_max_concepts():
    out = CorpusOutput(concepts=[_concept(label_ko=f"개념{i}") for i in range(5)])
    kept, dropped = validate_concepts(out, {"afresh-01"}, max_concepts=3)
    assert len(kept) == 3
    assert [d["reason"] for d in dropped] == ["over_max_concepts"] * 2
