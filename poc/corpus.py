"""LLM#1 코퍼스 경계 — SPEC_V3 §6: 주간 기사+웹서치 → 검증된 concepts."""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from poc import config
from poc.analyze import _call
from poc.rss import load_articles

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
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": (r.get("text") or "")[:300],
        }
        for i, r in enumerate(crawl_results)
        if r.get("ok", True)
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


CORPUS_SYSTEM = """너는 캐시미어·니트웨어 MD를 위한 트렌드 코퍼스 큐레이터다.
입력 JSON에는 최근 1주 패션 에디토리얼 기사(articles), 웹서치 결과(websearch),
직전 주 개념 목록(prior_concepts)이 있다.

임무: 측정할 가치가 있는 트렌드 개념을 최대 {max_concepts}개 추출한다.

규칙:
- 각 개념의 source_refs에는 근거가 된 articles/websearch 항목의 ref 값만 넣는다.
  입력에 없는 ref를 지어내면 그 개념은 폐기된다.
- naver_queries는 한국 소비자가 실제 검색할 한국어 검색어 1~3개.
  한국어 쿼리가 없으면 그 개념은 폐기된다.
- category는 소재/아이템/실루엣/컬러/테마 중 하나.
- prior_concepts에 있던 개념도 이번 주 근거가 있으면 다시 포함한다(연속 측정).
- 일반어(니트, 스웨터 단독)보다 구체 개념(포인텔 니트, 크롭 카디건)을 우선한다.
"""


def run_corpus(bundle: dict, valid_refs: set[str]) -> tuple[list[Concept], list[dict]]:
    raw = _call(
        CORPUS_SYSTEM.format(max_concepts=config.MAX_CONCEPTS),
        json.dumps(bundle, ensure_ascii=False),
        CorpusOutput,
    )
    return validate_concepts(raw, valid_refs)


def main(now: datetime | None = None) -> dict:
    articles = load_articles()
    crawl_path = config.OUT_DIR / "crawl_results.json"
    crawl = json.loads(crawl_path.read_text()) if crawl_path.exists() else []
    prior_path = config.OUT_DIR / "concepts.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else []

    bundle, valid_refs = build_corpus_input(articles, crawl, prior, now=now)
    try:
        kept, dropped = run_corpus(bundle, valid_refs)
    except Exception as exc:
        # LLM#1 실패 → 직전 주 concepts 유지 (SPEC_V3 §4 실패 격리)
        return {"concepts": len(prior), "dropped": 0, "fallback": f"{type(exc).__name__}: {exc}"}

    if not kept:
        # 전량 폐기 → concepts.json 덮어쓰지 않고 직전 주 유지, 진단만 기록 (SPEC_V3 §15 fallback guarantee)
        (config.OUT_DIR / "concepts_dropped.json").write_text(
            json.dumps(dropped, ensure_ascii=False, indent=2)
        )
        return {
            "concepts": len(prior),
            "dropped": len(dropped),
            "fallback": "all_concepts_dropped",
        }

    concepts = [c.model_dump() for c in kept]
    prior_path.write_text(json.dumps(concepts, ensure_ascii=False, indent=2))
    (config.OUT_DIR / "concepts_dropped.json").write_text(
        json.dumps(dropped, ensure_ascii=False, indent=2)
    )
    return {"concepts": len(concepts), "dropped": len(dropped)}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
