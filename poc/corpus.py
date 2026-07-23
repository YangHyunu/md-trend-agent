"""LLM#1 코퍼스 경계 — SPEC_V3 §6: 주간 기사+웹서치 → 검증된 concepts."""

import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from poc import config

WINDOW_DAYS = 7


class Concept(BaseModel):
    label_ko: str
    label_en: str
    aliases: list[str] = Field(default_factory=list)
    category: Literal["소재", "아이템", "실루엣", "컬러", "테마"]
    naver_queries: list[str]
    source_refs: list[str]
    rationale: str


class CorpusOutput(BaseModel):
    concepts: list[Concept]


_HANGUL = re.compile(r"[가-힣]")


def validate_concepts(
    output: CorpusOutput,
    valid_refs: set[str],
    max_concepts: int | None = None,
) -> tuple[list[Concept], list[dict]]:
    max_concepts = max_concepts or config.MAX_CONCEPTS
    kept: list[Concept] = []
    dropped: list[dict] = []
    for c in output.concepts:
        refs = [r for r in c.source_refs if r in valid_refs]
        if not refs:
            dropped.append({"label_ko": c.label_ko, "reason": "no_valid_source_refs"})
            continue
        queries = [q for q in c.naver_queries if _HANGUL.search(q)]
        if not queries:
            dropped.append({"label_ko": c.label_ko, "reason": "no_korean_query"})
            continue
        kept.append(c.model_copy(update={"source_refs": refs, "naver_queries": queries}))
    if len(kept) > max_concepts:
        for c in kept[max_concepts:]:
            dropped.append({"label_ko": c.label_ko, "reason": "over_max_concepts"})
        kept = kept[:max_concepts]
    return kept, dropped


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
