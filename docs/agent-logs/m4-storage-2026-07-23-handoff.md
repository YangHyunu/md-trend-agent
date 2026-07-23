# M4 저장+주간 델타 착수 Handoff (2026-07-23)

> Worktree: `.worktrees/m4-storage` (branch `feature/m4-storage`, base main cb3c73f).
> 이 세션은 **worktree** — 글로벌 auto-memory 읽기전용(CLAUDE.md §6.1). MEMORY.md 쓰기 금지.

## 목표 (SPEC_V3 §9)
3테이블 저장 + sqlite driver + 주간 델타 규칙. M2 병행 가능 명문(§12) — M3와 독립 병렬.

## 스키마 — 3테이블 (SPEC_V3 §9.1)
```sql
articles(id, source, url UNIQUE, title, published_at, fetched_at, matched_terms, excerpt, raw_path)
concepts(id, label_ko, label_en, aliases, category, first_seen_week, status, source_refs)
concept_weekly(concept_id, iso_week, naver_series, direction, delta_pct,
               supply_count, editorial_count, classification, run_id,
               PRIMARY KEY (concept_id, iso_week))
```
- 현 M1/M2는 파일 저장: `out/articles.jsonl`(rss), `out/concepts.json`(corpus), `out/merge_bundle.json`(weekly). M4가 이를 sqlite로 이관.
- `concept_weekly`가 선행/소멸 판정의 원천(시계열).

## 입력 계약 (M2 산출물 — main에 있음)
- `poc/bundle.py::MergeBundle` — concept_weekly 행의 원천. `ConceptMeasurement`에서: naver.series→naver_series, naver.direction→direction, naver.delta_pct→delta_pct, supply.supply_count→supply_count, editorial_count→editorial_count.
- `classification`은 **M3 산출**(claim 3분류). M4 빌드 단계엔 None/스텁 허용 — M3 착지 후 배선.
- articles/concepts는 `out/articles.jsonl` / `out/concepts.json` 형태 그대로 이관(rss.py/corpus.py 계약).

## driver 추상화 (SPEC_V3 §9.3)
SPEC은 인터페이스만 규정 — 백엔드는 driver 뒤:
```
put_article / upsert_concept / append_weekly
get_prior_weeks(concept_id, n) / similar_concepts(label)
```
- 1차: **sqlite** (로컬 파일1개, sqlite-vec/FTS5로 유사도 충분). 배포 전환 시 pgvector — 스키마 동일(벡터=컬럼1), 이관 얕음. 로컬/배포 최종결정 미확정 — driver 경계가 지연 가능케 함.
- **RAG/GraphRAG 채택 안함**(§14) — 볼륨 작음(연 1-2K), 누적 본질이 시계열. `similar_concepts`는 개념 중복방지 유사도 조회일 뿐 검색증강 아님.

## 주간 델타 규칙 (SPEC_V3 §9.2)
- concept **첫 주**: NAVER 시계열 자체 기울기(최근4주/직전4주)로 방향 — M2 `poc/measure.py::series_delta`가 이미 계산(direction/delta_pct). 그대로 저장.
- **다음 주부터**: 저장된 직전 주 대비 delta (get_prior_weeks 사용).
- 소량 베이스(직전 평균<3) △ 캡 — M2 series_delta의 small_base가 이미 처리. 퍼센트 과장 금지.

## 수용 기준 (SPEC_V3 §12 M4)
- 2주 연속 run에서 델타 산출; **동일 주 재실행 멱등**(dedup). articles url UNIQUE, concept_weekly PK(concept_id, iso_week) upsert.

## 병렬 조율 (M3와 공유)
- **유일 충돌점: `poc/weekly.py`.** M4는 weekly.run에 저장 배선 추가(번들 산출 후 put/upsert/append). M3는 합성 단계 추가. **나중 merge 쪽이 weekly.py 리베이스.** 저장을 독립 함수로 만들고 weekly.run에서 호출 — 경계 깔끔하면 리베이스 사소.
- `poc/config.py` append-only 상수 추가 — 충돌 없음.
- concept_weekly.classification은 M3 claim 산출 — M4는 컬럼만 준비, 값은 M3 배선 후.

## 테스트
sqlite는 결정론이라 일반 단위테스트 대상(§13). tmp_path에 파일 DB 생성, put→get 왕복, 멱등(2회 append 동일결과) 검증. 네트워크 없음.

## 시작
```
cd .worktrees/m4-storage
.venv/bin/python -m pytest -q   # 189 baseline 확인 (venv shebang 깨짐 — python -m 사용)
```
플랜: `superpowers:writing-plans`로 M4 플랜 작성 → subagent-driven 실행 권장(M1/M2 선례).
