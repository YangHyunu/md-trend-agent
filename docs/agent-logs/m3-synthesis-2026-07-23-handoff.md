# M3 Synthesis 착수 Handoff (2026-07-23)

> Worktree: `.worktrees/m3-synthesis` (branch `feature/m3-synthesis`, base main cb3c73f).
> 이 세션은 **worktree** — 글로벌 auto-memory 읽기전용(CLAUDE.md §6.1). MEMORY.md 쓰기 금지.

## 목표 (SPEC_V3 §8)
LLM#2 합성 경계 — merge 번들 → 검증/선행/소멸 3분류 claims + 수요-공급 갭 + 액션. + 결정론 validator + golden fixture.

## 입력 계약 (M2 산출물 — 이미 main에 있음)
- `poc/bundle.py::MergeBundle` (schema_version "3.0"). 필드: `iso_week`, `generated_at`, `concepts[ConceptMeasurement]`, `pinterest_category`, `supply_brands`, `coverage{axis: AxisCoverage}`.
  - `ConceptMeasurement`: `concept`(dict), `naver`(NaverMeasure|None), `supply`(SupplyMeasure|None), `editorial_count`(int).
  - `NaverMeasure`: series, delta_pct(None 가능), direction(up/down/flat/small_base/insufficient), recent_mean, prior_mean.
  - `SupplyMeasure`: supply_count(None=어휘갭 / 0=측정됐는데 공급없음=갭신호 / int), facets, unmeasurable.
- 실제 산출: `out/merge_bundle.json` (라이브 1건 있음, VPN시 supply 5/11). 파싱: `MergeBundle.model_validate_json(open("out/merge_bundle.json").read())`.
- 직전 주 `concept_weekly` 스냅샷 = **M4 산출물**. M3는 빌드 단계에선 fixture로 스텁(M4 미착지 상태에서 병렬 진행 가능). 통합은 M4 착지 후.

## 출력 계약 (SPEC_V3 §8.2, V2 §8.9 확장)
V2 Claim/AnalysisOutput 유지 + claim에 3분류 필드 추가:
- **validated**: 에디토리얼 히트 + NAVER 수요 상승/유의 (시장 반응 = 물량 판단)
- **leading**: 에디토리얼 히트 + NAVER 수요 0/미미 (빈자리 = MD 선점) — `editorial_count>0` + naver direction small_base/insufficient/flat
- **fading**: 직전 주 존재 + 에디토리얼 퇴장 + 수요 하락
- 추가: 수요-공급 갭(naver 상승인데 supply_count 희박/0), 액션 제안(V2 §14.3 근거 규칙).

## 결정론 validator (SPEC_V3 §8.3 — 서술은 LLM, 판정 정합은 결정론)
- 모든 claim EvidenceRef 필수 — 없으면 폐기.
- 숫자 주장(변동%, 수요 방향, 공급 수)은 validator가 **번들 원본과 대조** — 불일치 시 claim 폐기+로그.
- 3분류 경계값(수요 "미미" 기준 등)은 **config 상수**로 두고 validator가 분류-근거 정합 재검. (M2 선례: `config.SMALL_BASE_MEAN`/`DELTA_FLAT_BAND_PCT` 패턴 따를 것.)

## 수용 기준 (SPEC_V3 §12 M3)
3분류 출력; 전 claim EvidenceRef 보유; 숫자 claim validator 대조 통과; **라이브 run 1회 성공**. LLM 경계라 green 단위테스트가 runtime FAIL 은폐 가능(§13) — live-verify 필수.

## LLM 호출 방식
`poc/analyze.py::_call(system, user, output_format)` 재사용 (model claude-opus-4-8, ANTHROPIC_API_KEY env). M1 corpus(`poc/corpus.py::run_corpus`)가 선례 — pydantic output + validator 분리 패턴 그대로.

## 병렬 조율 (M4와 공유)
- **유일 충돌점: `poc/weekly.py`.** M3는 weekly.run 끝에 LLM#2 합성 단계 추가(번들 산출 후). M4도 weekly.run에 저장 배선 추가. **나중에 merge하는 쪽이 weekly.py 리베이스.** 합성/저장은 독립 함수로 만들고 weekly.run에서 순차 호출 — 함수 경계 깔끔하면 리베이스 사소.
- `poc/config.py` 양쪽 상수 추가 — append-only면 충돌 없음.
- M3 out claims → M4 concept_weekly.classification 컬럼에 저장됨. 계약: claim의 concept_id + classification.

## M2 이관 백로그 (M3에서 처리 후보)
- **label_ko 중복 concept 조인 last-wins** — bundle.assemble의 `by_group`이 label_ko 중복 시 마지막 시그널 채택. validator가 라벨 중복 폐기 검토.
- injected-client 헤더 변이(naver/pinterest) — M3가 client 공유 시 NAVER auth 헤더 누출 주의.

## 시작
```
cd .worktrees/m3-synthesis
.venv/bin/python -m pytest -q   # 189 baseline 확인 (venv shebang 깨짐 — python -m 사용)
```
플랜: `superpowers:writing-plans`로 M3 플랜 작성 → subagent-driven 실행 권장(M1/M2 선례).
