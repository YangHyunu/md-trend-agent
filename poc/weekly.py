"""weekly 분석 run (SPEC_V3 §5.2) — LLM#1 코퍼스 → 결정론 측정 3축 → 머지 번들.

축 실패는 격리(§4): 어떤 축이 죽어도 번들은 산출되고 CoverageMetrics에 남는다.
M3에서 LLM#2 합성이 이 뒤에 붙는다. python -m poc.weekly (cron: ops/cron.md).
"""
import json
from datetime import datetime, timezone

from datalayer.extract import extract_all
from poc import bundle, config, corpus, naver, pinterest


def _fail_result(call: str, exc: Exception) -> dict:
    return {"raw": {}, "signals": [],
            "failures": [{"call": call, "error": f"{type(exc).__name__}: {exc}"}]}


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    config.OUT_DIR.mkdir(exist_ok=True)

    corpus_status = corpus.main(now=now)
    concepts_path = config.OUT_DIR / "concepts.json"
    concepts = json.loads(concepts_path.read_text()) if concepts_path.exists() else []

    try:
        naver_result = naver.fetch_concept_trends(concepts)
    except Exception as e:
        naver_result = _fail_result("concept_trend", e)
    try:
        pinterest_result = pinterest.fetch_categories()
    except Exception as e:
        pinterest_result = _fail_result("pinterest_category", e)
    supply_error = None
    try:
        extraction = extract_all(config.BRANDS)
    except Exception as e:
        extraction, supply_error = [], f"{type(e).__name__}: {e}"

    merged = bundle.assemble(concepts, naver_result, pinterest_result, extraction,
                             now=now, supply_error=supply_error)
    payload = merged.model_dump_json(indent=2)
    (config.OUT_DIR / "merge_bundle.json").write_text(payload, encoding="utf-8")
    weekly_dir = config.OUT_DIR / "weekly"
    weekly_dir.mkdir(exist_ok=True)
    (weekly_dir / f"merge_bundle_{merged.iso_week}.json").write_text(payload, encoding="utf-8")

    return {
        "corpus": corpus_status,
        "iso_week": merged.iso_week,
        "concepts": len(merged.concepts),
        "coverage": {k: v.ratio for k, v in merged.coverage.items()},
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
