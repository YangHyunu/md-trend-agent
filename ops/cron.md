# 수집·분석 스케줄 (SPEC_V3 §5)

2계층 cadence: 수집 daily / 분석 weekly. 스케줄러는 외부(cron/launchd) — 코드는
멱등 CLI만 제공한다(재실행 안전: RSS는 URL dedup, 코퍼스는 파일 덮어쓰기).

## daily — RSS poll

    0 9 * * * cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.rss >> out/rss_poll.log 2>&1

## weekly — 코퍼스 (분석 run의 1단계, M2에서 전체 파이프라인으로 확장)

    0 10 * * 1 cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.corpus >> out/corpus_run.log 2>&1

- weekly 요일은 config 취급(SPEC_V3 §5.2) — 현재 월요일 10:00 KST.
- LLM·API 예산은 weekly run에만 발생(V2 §21).
