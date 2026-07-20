# 캐시미어·니트웨어 MD 트렌드 에이전트 PoC 명세

## 1. 문서 상태

- 기준일: 2026-07-20
- 단계: PoC (MVP 이전 가치 검증)
- 상위 문서: `SPEC.md` (MVP 명세, 보존)
- 실행 방식: CLI 단일 스크립트
- 저장소: JSON 파일 덤프

이 문서는 PoC 구현 기준이다. MVP 명세(`SPEC.md`)의 아키텍처 요구(Hermes, Discord, FastAPI, SQLite, 상태머신, 정책 검증기, Docker)는 PoC에 적용하지 않는다.

## 2. 목적

**검증 질문 하나: "이 파이프라인이 만든 보고서가 MD에게 실제로 쓸모 있는가?"**

NAVER 수요 데이터 + 공개 웹 수집 + LLM 분석으로 근거가 연결된 상품 기획 보고서를 만들고, MD가 읽고 유용성을 판정한다. 유용하면 MVP 투자 근거 확보. 아니면 SPEC.md를 수정한다.

아키텍처 품질, 운영 안정성, UX는 검증 대상이 아니다.

## 3. 범위

### 포함

- `cashmere-reference` 브랜드 세트 (config 하드코딩, SPEC.md §10과 동일)
- NAVER API HUB: Search Trend + Shopping Insight 각 1~3회 호출
- Tavily 웹 검색으로 보조 URL 발견
- Crawl4AI로 브랜드 공식몰 + 발견 URL 수집
- LLM 분석 2패스: 리서처(사실 정리) → MD 분석가+에디터(트렌드·제안, 근거 연결)
- 모든 주요 주장에 근거 ID 연결, 근거 없으면 `근거 없음` 표시
- Markdown 보고서 1장 (Design Map 매트릭스 포함)
- 중간 산출물 전부 JSON 덤프 (재실행·디버깅용)

### 제외

- Hermes Agent, Discord, FastAPI, SQLite, Docker
- 계획 승인 흐름, plan_version, 상태머신, lease/heartbeat
- Browser Use fallback (Crawl4AI 실패 = 실패 기록만)
- 보완 수집 루프, 근거 감사자
- HTML 보고서, sanitizer, 썸네일 proxy
- 테스트 스위트 (스모크 실행이 곧 테스트)
- Instagram (PLUSH'MERE는 reference_only, 수집 안 함)

## 4. 실행 흐름

```text
python -m poc.run
→ config 로드 (브랜드, 키워드, 분석 조건)
→ NAVER Search Trend + Shopping Insight 호출
→ Tavily 검색 → 후보 URL
→ Crawl4AI 수집 (공식몰 + 후보 URL)
→ 근거 JSON 생성 (evidence id 부여)
→ LLM 패스 1: 리서처 — 사실·수치·발췌 정리
→ LLM 패스 2: MD 분석가 — 트렌드·Design Map·MD 액션, 근거 ID 연결
→ Markdown 보고서 렌더
→ out/ 에 보고서 + 모든 중간 JSON 저장
```

## 5. 고정 분석 조건

- 카테고리: 여성 니트웨어 (캐시미어 중심)
- 타깃: 한국 여성 25~39세
- 가격대: 20만~70만원
- 기간: 최근 8주
- 중점: 경쟁 아이템, 컬러 조합, 주요 소재, 독특한 캐시미어 아이템

## 6. 기술 제약 (SPEC.md에서 유지하는 것)

PoC라도 도메인 정확성은 지킨다.

- NAVER API HUB만 사용 (`https://naverapihub.apigw.ntruss.com`, 구 openapi.naver.com DataLab 금지)
- 인증: `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`
- `ratio`는 상대값 — 서로 다른 요청 간 절대 비교 금지, 보고서에 명시
- 연령 코드: Search Trend 25~39세 = `4,5,6` / Shopping Insight 20~39세 = `20,30`, 혼용 금지
- Shopping Insight의 `coverage_mismatch` (25~39 요청 vs 20~39 관측) 보고서 의무 표시
- 공개 `http/https` URL만 수집, 로그인·CAPTCHA·SNS 자동 수집 금지
- 원문 전체 재배포 금지 — 발췌 + 출처 링크만

## 7. 예산 (하드코딩 상수)

- Tavily 검색 질의: 최대 8개
- 수집 URL: 최대 20개 (공식몰 11 + 발견 URL)
- NAVER 호출: 최대 6회
- Crawl4AI timeout: URL당 60초
- LLM 호출: 패스당 1회 (스키마 실패 시 재시도 1회)

초과 시 자르고 진행. 예외로 죽지 않는다.

## 8. 산출물

```text
out/
  evidence.json        # 근거 목록 (id, url, 발췌, 브랜드, 가격 등)
  naver_raw.json       # NAVER 원응답
  crawl_results.json   # URL별 성공/실패 + 추출 텍스트
  researcher.json      # 패스 1 출력
  analysis.json        # 패스 2 출력 (주장 + 근거 ID)
  report.md            # 최종 보고서
```

### 보고서 구조 (report.md)

1. 핵심 요약
2. 수요 신호 (NAVER, ratio 상대값 주의문 포함)
3. Design Map — 브랜드 × (핵심 아이템 / 컬러 / 소재 / 실루엣 / 디테일 / 가격대) 매트릭스, 셀마다 근거 ID
4. 트렌드 (상승/주류/포화/둔화)
5. 상품 구성 공백과 기회
6. MD 추천 액션 (근거 ID 연결, 3개 이상 목표)
7. 데이터 한계와 수집 실패 목록
8. 출처 목록 (id, URL, 수집일)

## 9. 코드 구조

```text
poc/
  config.py    # 브랜드 세트, 키워드, 분석 조건, 예산 상수
  naver.py     # API HUB 클라이언트 (인증, 연령코드, 정규화)
  collect.py   # Tavily 검색 + Crawl4AI 수집
  analyze.py   # LLM 2패스 (Pydantic 스키마 입출력)
  report.py    # Markdown 렌더 (코드가 렌더, LLM 자유 생성 금지)
  run.py       # 순차 실행 entry point
```

의존성: `httpx`, `crawl4ai`, `tavily-python`, `pydantic`, LLM SDK 1개.

## 10. 성공 기준

- `python -m poc.run` 한 번으로 report.md가 나온다
- 보고서에 NAVER 수요 신호가 최소 1개 포함되거나 실패 이유가 표시된다
- 수집 성공 URL이 5개 이상이다
- 모든 MD 액션과 Design Map 셀에 근거 ID가 있거나 `근거 없음`이 표시된다
- 수집 실패 URL과 원인이 보고서에 나온다
- **MD(사용자)가 보고서를 읽고 유용성을 판정할 수 있다** ← 최종 기준

## 11. PoC 이후

- 유용 판정 → SPEC.md 기반 MVP 착수 (승인 흐름, Hermes, 저장소, 안전장치)
- 미흡 판정 → 부족한 지점(데이터? 분석 품질? 보고서 형식?)을 SPEC.md에 반영 후 재시도
- PoC 코드는 MVP에 그대로 승격하지 않는다. `naver.py`, `collect.py`의 로직만 이식 후보다.
