import json
from datetime import datetime, timezone

from poc import config, corpus
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
    crawl = [
        {"url": "https://blog/0", "ok": False, "text": "dead", "title": "실패"},
        {"url": "https://blog/1", "ok": True, "text": "x" * 500, "title": "올가을 니트"},
    ]
    prior = [{"label_ko": "포인텔 니트", "label_en": "pointelle knit",
              "category": "소재", "aliases": [], "naver_queries": ["포인텔"],
              "source_refs": ["a-old"], "rationale": "지난주"}]

    bundle, valid_refs = build_corpus_input(articles, crawl, prior, now=_NOW)

    assert [a["ref"] for a in bundle["articles"]] == ["afresh-01"]
    assert len(bundle["websearch"]) == 1  # 실패 크롤은 제외
    assert bundle["websearch"][0]["ref"] == "w1"  # 원본 리스트 위치 인덱스 유지
    assert len(bundle["websearch"][0]["content"]) == 300
    assert "query" not in bundle["websearch"][0]
    assert bundle["prior_concepts"] == [
        {"label_ko": "포인텔 니트", "label_en": "pointelle knit", "category": "소재"}
    ]
    assert valid_refs == {"afresh-01", "w1"}


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


def _seed_articles(monkeypatch, tmp_path):
    articles_path = tmp_path / "articles.jsonl"
    articles_path.write_text(
        json.dumps(_article("https://x/fresh-01", "2026-07-22T00:00:00+00:00")) + "\n"
    )
    monkeypatch.setattr(config, "ARTICLES_PATH", articles_path)
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)


def test_main_writes_validated_concepts(monkeypatch, tmp_path):
    _seed_articles(monkeypatch, tmp_path)
    monkeypatch.setattr(
        corpus, "_call",
        lambda system, user, fmt: CorpusOutput(concepts=[
            _concept(),
            _concept(label_ko="유령", source_refs=["ghost"]),
        ]),
    )

    summary = corpus.main(now=_NOW)

    saved = json.loads((tmp_path / "concepts.json").read_text())
    dropped = json.loads((tmp_path / "concepts_dropped.json").read_text())
    assert summary == {"concepts": 1, "dropped": 1}
    assert saved[0]["label_ko"] == "포인텔 니트"
    assert dropped[0]["reason"] == "no_valid_source_refs"


def test_main_falls_back_to_prior_on_llm_failure(monkeypatch, tmp_path):
    _seed_articles(monkeypatch, tmp_path)
    prior = [_concept().model_dump()]
    (tmp_path / "concepts.json").write_text(json.dumps(prior, ensure_ascii=False))

    def _boom(system, user, fmt):
        raise RuntimeError("api down")

    monkeypatch.setattr(corpus, "_call", _boom)

    summary = corpus.main(now=_NOW)

    assert summary["fallback"] == "RuntimeError: api down"
    assert summary["concepts"] == 1
    # 직전 주 파일은 무변경
    assert json.loads((tmp_path / "concepts.json").read_text()) == prior


def test_main_falls_back_when_all_concepts_dropped(monkeypatch, tmp_path):
    _seed_articles(monkeypatch, tmp_path)
    prior = [_concept().model_dump()]
    (tmp_path / "concepts.json").write_text(json.dumps(prior, ensure_ascii=False))

    monkeypatch.setattr(
        corpus, "_call",
        lambda system, user, fmt: CorpusOutput(concepts=[
            _concept(label_ko="유령", source_refs=["ghost"]),
        ]),
    )

    summary = corpus.main(now=_NOW)

    assert summary["fallback"] == "all_concepts_dropped"
    assert summary["concepts"] == 1
    # 직전 주 파일은 무변경
    assert json.loads((tmp_path / "concepts.json").read_text()) == prior
    dropped = json.loads((tmp_path / "concepts_dropped.json").read_text())
    assert dropped[0]["reason"] == "no_valid_source_refs"
