"""LLM#1 코퍼스 경계 — SPEC_V3 §6: 주간 기사+웹서치 → 검증된 concepts."""

from datetime import datetime, timedelta, timezone

WINDOW_DAYS = 7


def _recent(articles: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    return [a for a in articles if a["fetched_at"] >= cutoff]


def build_corpus_input(
    articles: list[dict],
    crawl_results: list[dict],
    prior_concepts: list[dict],
    now: datetime | None = None,
) -> tuple[dict, set[str]]:
    recent = _recent(articles, now)
    web = [
        {
            "ref": f"w{i}",
            "query": r.get("query", ""),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": (r.get("content") or "")[:300],
        }
        for i, r in enumerate(crawl_results)
    ]
    bundle = {
        "articles": [
            {
                "ref": a["id"],
                "source": a["source"],
                "title": a["title"],
                "published_at": a["published_at"],
                "matched_terms": a["matched_terms"],
                "excerpt": a["excerpt"],
            }
            for a in recent
        ],
        "websearch": web,
        "prior_concepts": [
            {"label_ko": c["label_ko"], "label_en": c["label_en"], "category": c["category"]}
            for c in prior_concepts
        ],
    }
    valid_refs = {a["ref"] for a in bundle["articles"]} | {w["ref"] for w in web}
    return bundle, valid_refs
