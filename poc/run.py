"""PoC 전체 파이프라인. python -m poc.run"""
import json
import sys

from poc import collect, config, naver, report
from poc.analyze import run_analyst, run_researcher
from datalayer.aggregate import brand_aggregate
from datalayer.extract import extract_all


def _dump(name: str, data) -> None:
    (config.OUT_DIR / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    config.OUT_DIR.mkdir(exist_ok=True)

    print("[1/4] NAVER 수요 신호 수집...")
    try:
        naver_result = naver.fetch_all()
    except Exception as e:  # 인증키 부재 등 — 부분 실패로 계속 진행
        naver_result = {"raw": {}, "signals": [],
                        "failures": [{"call": "all", "error": f"{type(e).__name__}: {e}"}]}
    _dump("naver_raw.json", naver_result)
    print(f"  signals={len(naver_result['signals'])} failures={len(naver_result['failures'])}")

    print("[2/4] 웹 검색 + 크롤링...")
    crawl_results, evidence = collect.collect()
    _dump("crawl_results.json", crawl_results)
    _dump("evidence.json", evidence)
    ok = sum(r["ok"] for r in crawl_results)
    print(f"  crawled ok={ok}/{len(crawl_results)} evidence={len(evidence)}")
    if not evidence and not naver_result["signals"]:
        print("근거 0건 — 실패 기록 중심의 보고서로 계속 진행.", file=sys.stderr)

    print("[2b] datalayer 상품 실측 (Shopify 직수집)...")
    dl_aggregates = [brand_aggregate(r) for r in extract_all(config.BRANDS)]
    _dump("datalayer_aggregates.json", dl_aggregates)
    ok_dl = sum(1 for a in dl_aggregates if a.get("count"))
    total_prod = sum(a.get("count", 0) for a in dl_aggregates)
    print(f"  datalayer 성공 {ok_dl}/{len(dl_aggregates)}몰, 상품 {total_prod}개")

    print("[3/4] LLM 분석 (2패스)...")
    researcher = run_researcher(evidence, naver_result["signals"])
    (config.OUT_DIR / "researcher.json").write_text(
        researcher.model_dump_json(indent=2), encoding="utf-8")
    analysis = run_analyst(researcher, evidence, naver_result["signals"])
    (config.OUT_DIR / "analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8")
    print(f"  facts={len(researcher.facts)} trends={len(analysis.trends)} "
          f"actions={len(analysis.actions)}")

    print("[4/4] 보고서 렌더링...")
    md = report.render_report(analysis, naver_result, crawl_results, evidence,
                              datalayer_aggregates=dl_aggregates)
    (config.OUT_DIR / "report.md").write_text(md, encoding="utf-8")
    print(f"완료: {config.OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
