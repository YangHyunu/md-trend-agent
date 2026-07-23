# 수집·분석 스케줄 (SPEC_V3 §5)

2계층 cadence: 수집 daily / 분석 weekly. 스케줄러는 외부(cron/launchd) — 코드는
멱등 CLI만 제공한다(재실행 안전: RSS는 URL dedup, 코퍼스는 파일 덮어쓰기).

## daily — RSS poll

    0 9 * * * cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.rss >> out/rss_poll.log 2>&1

## weekly — 분석 run (코퍼스 → 측정 3축 → 머지 번들)

    0 10 * * 1 cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.weekly >> out/weekly_run.log 2>&1

- weekly 요일은 config 취급(SPEC_V3 §5.2) — 현재 월요일 10:00 KST.
- LLM·API 예산은 weekly run에만 발생(V2 §21). M2 기준 LLM 호출은 corpus(LLM#1) 1회뿐.
- M3(LLM#2 합성)가 이 run 뒤에 붙는다.
