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

## 12. MVP 데이터 레이어 재설계 (2026-07-20, PoC 실측 기반)

> PoC report의 "근거 없음" 셀 폭증 원인을 실측 진단해 확정한 설계.
> **원인:** PoC `collect.py`는 브랜드 홈페이지 1페이지의 앞 3,000자 markdown만 수집 →
> 컬러·가격·소재·실루엣은 상품 상세페이지에 있어 랜딩엔 부재. 분석 품질 아닌 **크롤 깊이 문제.**
> 이 §12는 SPEC.md §5(Crawl4AI, Web Discovery, NAVER)·§6(Content Collector, DataLab Client,
> Analysis Skills)를 **구체화·대체**한다. 아래 결정은 owner와 합의·확정(LOCK)됨.

### 12.1 소스 획득 사다리 (브랜드별 코드 0, 순서대로 시도·첫 성공 채택)

1. **플랫폼 피드** — Shopify `/products.json` (WooCommerce `/wp-json` 등). **페이지네이션 필수**
   (250/page 상한, 빈 페이지까지 `?page=N` 루프. 미이행 시 조용히 잘림 — arch4 실측 500+).
   공개(published) 상품 전량. 재고 수량·metafield 제외.
2. **sitemap.xml** — 상품 URL 수집 (index→gzip→하위 sitemap 처리 포함, 예 Iris/Shopware).
3. **페이지 구조화** — 상세페이지 JSON-LD `schema.org/Product`(범용 표준) 또는
   `__NEXT_DATA__`/`__NUXT__` 임베드 상태(예 Quince Next.js).
4. **렌더 크롤 + LLM** — crawl4ai 헤드리스로 JS 렌더/봇차단 시도. 최후 폴백.

- **httpx = ①②③ 처리(싸고 빠름). crawl4ai = ④ 전용**(JS렌더 or 봇차단 뚫기, 보장 아님).
- **하드 봇차단(예 COS 403)은 포기 + 커버리지/실패 명시.** NAVER·크롤 실패와 동일 원칙.
- 실측 통화/구조: Shopify 6몰(guestinresidence·lisayang=USD, extreme=EUR, &daughter·arch4·cashmereinlove=GBP). 비Shopify: Quince(Next.js), Iris(Shopware sitemap), LE17(sitemap 없음), COS(봇차단).

### 12.2 필드별 폴백 사다리 (브랜드별 코드 0)

필드 하나당: **① 구조화 시도(코드) → ② 없으면 LLM이 raw 레코드서 추출 → ③ 원본 substring 검증(날조 차단).**

| 필드 | 1차(구조화) | 2차(폴백) | 검증 |
|---|---|---|---|
| 가격 | variants.price + `compare_at_price`(세일감지) + shop 통화 | — (**항상 코드만, LLM 금지**) | — |
| 아이템 | product_type | 제목/태그서 LLM | — |
| 컬러 | options `color`/`colour`(철자 방어) | 태그/제목서 LLM 색토큰 추출 | **원본 substring 존재 확인** |
| 소재/신상 | tags·body_html·published_at | — | — |

- lisayang처럼 색이 tags에 노이즈와 섞인 경우 → 폴백 사다리가 자동 흡수, 코드에 브랜드명 0줄.

### 12.3 정규화

- **통화(KEXIM 한국수출입은행 AP01):** 일 1회 **KST 10:00** 잡 → `fx_cache.json`. 파이프라인은 캐시만 읽음.
  통화 USD/EUR/GBP. `deal_bas_r` 콤마 제거, 전부 per-1. **실패/빈응답(주말·공휴일·미고시) → 직전 영업일 값** + report 주석.
  (KEXIM 첫 고시 ~11시라 10시 호출은 직전일 값 자주 사용 — 의도된 동작.) authkey = **오너 발급 액션.**
  집계 밴드경계(p25/50/75)만 환산, native+KRW 병기.
- **컬러(고정 8계열):** 뉴트럴 / 베이지·카멜·브라운 / 블루·네이비 / 그린 / 레드·핑크 / 옐로·오렌지 / 퍼플 / 멀티·패턴.
  매핑 = **LLM 증분 분류**(처음 보는 컬러명만 LLM에 → `color_map.json` 캐시 병합, 기존 재사용) + **사람 수동 교정 가능**.
  계열은 닫힌 집합 강제(LLM이 새 계열 생성 금지). 원색명 빈도는 코드가 병행 집계.
  근거: 6몰 실측 컬러명 파편화 — distinct 다수가 단일 브랜드 전용, 겹치는 건 기본색뿐 → raw로 크로스브랜드 비교 불가.

### 12.4 집계 스키마 (코드가 100% 확정, LLM은 해석만 → evidence 날조 불가)

**브랜드 블록(~11줄):** source · coverage{products, color_missing, failures} · currency(fx날짜) ·
items(product_type 분포) · colors_fam(8계열) · colors_raw(top10 참고) ·
price_krw{p25/p50/p75/min/max} · price_band · sale(비율) · materials(키워드) · newness(최근8주 신상수, 최근드롭일).

**크로스브랜드 롤업:** category · covered(N/총) + 실패·제외 · item core · palette · pricing(구간별 분포) · newness · gaps.

- **가격 밴드:** 저가 <20만 / 타깃 20~70만 / 프리미엄 >70만.
- **신상 창 = 최근 8주** (분석창과 일치, published_at 기준).
- **결측을 데이터로:** coverage/failures/gaps 필드가 "없음"을 명시 → LLM 빈칸 날조 방지.

### 12.5 NAVER 축 (수요 신호 — 정량 + 정성)

**12.5.1 401 해결 (2026-07-20 실측):** 근본원인은 키 무효 아니라 **`.env` 변수명 오류**.
오너가 값을 HTTP 헤더명(`X-NCP-APIGW-API-KEY-ID`)으로 넣었는데 코드는 env 변수명
(`NCP_API_HUB_CLIENT_ID`)을 읽음. 변수명 rename 후 **3콜 전부 200. 키 처음부터 유효**
(NCP API HUB 키). `SHOPPING_CAT_ID="50000804"`도 live 검증됨("여성 니트/스웨터").
초기 "키 무효" 진단은 오답이었음.

**12.5.2 정량 소스 3콜 (연령코드 체계 실측 확정):**
- **Search Trend** `ages=["4","5","6"]` = **25-39 정확** (검색량 기반, 카테고리 무관).
  캐시미어 니치 수요는 **이 축이 유일하게 신뢰**. 8포인트 시계열 정상.
- **shopping/categories** `ages=["20","30"]` = 20-39 (Shopping Insight는 10년버킷만,
  25-39 표현 불가 — coverage_mismatch 주석). 카테고리 클릭 추이. 정상.
- **shopping/category/keywords → gender/ages 제거(LOCK, 2026-07-20 A).**
  실측: f+20/30 필터 시 캐시미어 세부어(캐시미어니트·가디건·스웨터·코트) 전부 `data:[]`.
  필터 제거해도 세부어는 0(카테고리 내 클릭량 집계임계 미달), 광범위어(여성니트)만 4포인트.
  → **필터 제거로 광범위어라도 확보**, 캐시미어 세부 수요는 Search Trend에 의존.

**12.5.3 정성 소스 — Blog Search (신규, 2026-07-20 LOCK):**
- **`GET /search/v1/blog`** (base `https://naverapihub.apigw.ntruss.com`, **같은 NCP 키**).
  live 검증: status 200, total 7만+, `sort=date` 최신순, items{title, description, postdate,
  bloggername, link}. 오너가 NCP 콘솔서 같은 앱에 블로그검색 구독 추가함(새 키 불요).
- 용도: **한국 소비자 정성 목소리**(컬러조합·간절기 코디·브랜드 언급) → report가 깐
  "한국 타깃 정합 불가"·"컬러조합 근거 전무" 갭 메움. Tavily 네이버블로그 우연수집을 체계화.
- 정량(정성 아님) 축과 분리: DataLab=수요 크기, Blog=수요 내용.

**12.5.4 evidence-id 정책:** NAVER 정량 signals는 상대값이라 주장 근거 인용 불가 →
report §2 별도 블록 유지(현행). **Blog 결과는 URL·발췌 있으니 evidence(E###) 부여 대상**
(웹크롤 evidence와 동일 취급, Design Map/트렌드 인용 가능). 정량 signals와 정성 evidence 구분.

- 코드(`poc/naver.py`)는 실패를 report §7에 기록하고 계속 진행 — 실패 폴백 원칙 유지.
