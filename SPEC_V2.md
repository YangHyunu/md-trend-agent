# 캐시미어·니트웨어 MD 트렌드 에이전트 Hermes MVP 명세 v2

## 1. 문서 상태

- 기준일: 2026-07-22
- 문서 버전: 2.0
- 단계: Hermes MVP 구현 기준(출시 gate = Phase 0A·0B·0C + Phase 1)
- 제품명: `md-trend-agent`
- 검증 엔진: `md-trend-sniper`(현재 `poc/`, `datalayer/`)
- 사용자 인터페이스: Hermes Desktop 우선, Discord 후속
- 에이전트 런타임: Hermes Agent
- 구현 에이전트: Claude / Claude Code(Codex 제외)
- 결정론적 도메인 코어: Python
- 초기 실행 저장: run-scoped JSON/Markdown/HTML
- 내구성 저장: SQLite, Discord 단계에서 도입

이 문서는 기존 `SPEC.md`의 목표 제품 구조와 `POC_SPEC.md`의 실측 결과를 통합한 새 구현 기준이다. 기존 문서는 설계 이력으로 보존한다.

핵심 변경은 다음과 같다.

1. 배포된 `https://yanghyunu.github.io/md-trend-agent/`와 그 production snapshot을 제품의 canonical golden 산출물로 고정한다.
2. 대형 운영 구조를 한 번에 만들지 않고 리포트 엔진, Hermes 승인 흐름, SQLite 내구성, 운영 서비스 순서로 확장한다.
3. 상품 실측, 국내 수요, 런웨이, 에디토리얼 근거를 하나의 `AnalysisInput`으로 통합한다.
4. Shopify 단일 소스에서 브랜드별 `Source Registry`와 Scrapling 기반 수집 사다리로 확장한다.
5. 주요 주장과 MD 액션 모두 evidence ID를 가져야 한다.
6. 완전 실패와 부분 실패도 결정적인 HTML 보고서로 남긴다.

### 1.1 규범 용어

- **필수/MUST**: 해당 Phase의 수용 조건이다.
- **권장/SHOULD**: 특별한 이유가 없으면 구현한다. 미구현 이유를 기록한다.
- **선택/MAY**: 제품 가치와 운영 필요가 확인된 뒤 구현한다.

### 1.2 현재 구현과 목표의 차이

이 문서는 현재 코드가 이미 만족하는 상태를 설명하지 않는다. 2026-07-22 현재 주요 차이는 다음과 같다.

- `poc/config.py`에는 Le Cashmere가 자동 수집 대상으로 남아 있고 PLUSH’MERE는 `auto_collect=False`다.
- `datalayer/records.py`의 `ProductRecord`는 flat price와 compare-at 값을 사용하며 variant 전체 계약이 없다.
- `poc/analyze.py`는 NAVER signal과 기존 evidence만 받고 datalayer aggregate, steady, coverage, failures를 받지 않는다.
- 기존 숫자 authority tier와 본 문서의 A/B/C tier가 다르다.
- Source Registry, 비-Shopify 전용 adapter, editorial feed collector, contradiction auditor, Hermes skill, atomic CLI는 아직 구현되지 않았다.
- 배포된 report는 시각·정보 구조·MD 활용성의 비회귀 기준이며 새 계약과 renderer가 이를 축소하거나 대체할 수 없다.

각 Phase 구현은 이 차이를 테스트로 제거해야 한다.

### 1.3 마일스톤 명칭과 종료점

- **Phase 0A/0B/0C**: Hermes가 아닌 report-engine engineering milestone
- **Hermes MVP**: Phase 0A·0B·0C와 Phase 1 수용 기준을 모두 통과한 Desktop 제품
- **Operational MVP**: Hermes MVP에 Phase 2의 Discord·SQLite·복구를 더한 제품; 기존 `SPEC.md`의 MVP와 대응
- **Phase 3**: 검증 후 선택하는 scale-out

Phase 0 단독 완료를 “Hermes MVP 완료”라고 부르지 않는다. Phase 1 구현은 0A 통과 후 병렬 착수할 수 있지만 Hermes MVP 출시는 0C까지 통과해야 한다.

---

## 2. 제품 비전

`md-trend-agent`는 패션 정보를 많이 모으는 검색 봇이 아니다.

> 흩어진 런웨이, 에디토리얼, 상품, 가격, 국내 수요 데이터를 감사 가능한 MD 의사결정으로 변환하는 Hermes Agent다.

사용자가 묻는 질문은 다음과 같다.

```text
2026 FW 여성 캐시미어 시장에서
어떤 컬러, 아이템, 소재, 실루엣, 가격 구성을 가져가야 하는가?
```

제품은 다음을 한 리포트에 연결한다.

- 경쟁 브랜드의 현재 판매 상품
- 가격, 할인, 컬러, 소재, 아이템, 실루엣 실측
- NAVER 기반 국내 수요 신호
- Vogue Runway 등 런웨이 관측
- Fashionista, Highsnobiety 등 편집 매체 해석
- 브랜드 시그니처와 상품 구성 공백
- 데이터 커버리지와 실패
- 실행 가능한 MD 액션
- 모든 주요 판단의 근거 URL과 evidence ID

성공은 “그럴듯한 보고서”가 아니라 MD가 다음 상품 기획 행동을 선택할 수 있는지로 판정한다.

---

## 3. 제품 계층

### 3.1 `md-trend-sniper`

현재 `poc/`와 `datalayer/`에 있는 수직 슬라이스다.

목적:

- 리포트의 MD 가치 검증
- 상품 데이터 수집 가능성 검증
- 보고서 정보 구조 검증
- 데이터 계약과 분석 품질 개선

### 3.2 `md-trend-agent`

sniper 엔진을 도메인 코어로 사용하는 운영형 제품이다.

추가 기능:

- Hermes 자연어 요청 구조화
- 조사 계획 생성·수정·승인
- 정책 검증
- 단계 오케스트레이션
- 근거 감사와 보완 수집
- Discord 입출력
- SQLite 실행 이력
- 취소, 재실행, 장애 복구

### 3.3 관계

```text
md-trend-agent
├── Hermes/Discord 제품 계층
├── 승인·정책·실행 상태 계층
└── md-trend-sniper 기반 리포트 도메인 코어
```

sniper는 폐기 대상이 아니다. agent가 호출하는 검증된 엔진으로 승격한다.

---

## 4. 설계 원칙

### 4.1 Evidence first

모든 주요 주장과 MD 액션은 유효한 evidence ID를 가져야 한다. 근거가 약하면 가설로 강등한다. 근거가 없으면 생성하지 않는다.

### 4.2 Human approval

Hermes가 수집 범위, 소스, 예산을 계획으로 제안한다. 사용자가 승인한 plan version만 실행한다.

### 4.3 Deterministic core

Python이 담당한다.

- 수집
- 정규화
- 환율
- 중복 제거
- 집계
- 커버리지
- 정책 검증
- evidence ID
- 스키마 검증
- 모순 검사
- HTML/Markdown 렌더링

Hermes가 담당한다.

- 자연어 조건 이해
- 계획 제안·수정
- 조사 질문 설계
- 리서처·분석가·에디터 판단
- 근거 충분성 판단
- 보완 수집 결정
- 사용자 승인과 결과 전달

### 4.4 Partial failure is normal

일부 소스가 실패해도 가능한 분석을 계속한다. 실패를 숨기지 않는다. evidence가 0개여도 요청, 계획, 실패 목록을 포함한 `근거 수집 실패 보고서`를 만든다.

### 4.5 Coverage before volume

`1,904개 상품`만 표시하지 않는다. `성공 브랜드/대상 브랜드`, 필드 커버리지, 실패 소스를 함께 표시한다.

### 4.6 Thin Hermes

Hermes skill에는 절차와 판단 기준만 둔다. 계산과 비즈니스 규칙을 prompt에 숨기지 않는다.

### 4.7 Progressive architecture

FastAPI, 복잡한 상태머신, 다중 worker, lease, Docker 4서비스는 실제 동시 실행·복구 요구가 생긴 뒤 추가한다.

### 4.8 POC 자동수집 우선, 수동 fallback

sniper는 수집 가능성과 MD 가치를 검증하는 POC다. 공개·비로그인 페이지가 robots와 명시적 사이트 제한을 위반하지 않으면 [Scrapling](https://github.com/d4vinci/Scrapling)으로 bounded 자동수집을 실행할 수 있다. 모든 source에 written permission이 생길 때까지 자동수집을 일괄 금지하지 않는다.

다만 POC 자동수집과 production 지속수집을 구분한다. POC는 opt-in run, 작은 page/product/request cap, deadline, derived-only artifact를 사용한다. 예약·반복 수집, 장기 raw HTML·JSON·image 보존과 재배포는 source별 production contract 이후 활성화한다. adapter 실패 또는 `manual_only` source는 정상 브라우저 기반 수동 URL-linked observation으로 보완하며, CAPTCHA·WAF·로그인·paywall·명시적 block은 자동·수동 모두 우회하지 않는다.

---

## 5. 사용자와 핵심 시나리오

### 5.1 주 사용자

- 여성 캐시미어·니트웨어 브랜드 MD
- 상품기획자
- 브랜드 전략 담당자

### 5.2 기본 분석 조건

```yaml
category: 여성 니트웨어
focus: 캐시미어
market: KR
target_age: 25-39
price_range_krw: [200000, 700000]
window: 최근 8주
season: 사용자 지정 또는 현재 기획 시즌
focus_dimensions:
  - item
  - color
  - material
  - silhouette
  - detail
  - price
```

### 5.3 요청 예

```text
cashmere-reference 브랜드 세트로 26FW 조사해줘.
한국 여성 25~39세, 20만~70만원.
컬러, 아이템, 소재, 실루엣, 가격 공백을 보고 싶어.
```

### 5.4 사용자 흐름

1. 사용자가 Hermes Desktop 또는 Discord에 요청한다.
2. Hermes가 `AnalysisRequest` 초안을 만든다.
3. Hermes가 Source Registry와 예산을 이용해 `CollectionPlan`을 만든다.
4. Python policy validator가 계획을 검사한다.
5. Hermes가 plan version, 소스, 예상 비용, 제외 항목을 사용자에게 보여준다.
6. 사용자가 승인, 수정, 취소한다.
7. 승인된 계획으로 공개 source를 Scrapling 자동수집하고 adapter 실패 또는 `manual_only` source는 수동 관찰 task로 전환한다.
8. Python이 정규화·집계·커버리지 계산을 수행한다.
9. Hermes가 근거를 감사하고 필요 시 보완 수집을 한 번 요청한다.
10. Hermes가 리서처, MD 분석가, 에디터 단계를 실행한다.
11. Python이 출력 스키마, evidence 연결, 모순을 검증한다.
12. Python이 Markdown과 HTML을 렌더링한다.
13. Hermes가 핵심 요약, 실패, 산출물을 사용자에게 전달한다.

---

## 6. 단계별 범위

### Phase 0 — 리포트 엔진 engineering milestones

한 번에 완료하는 단일 gate가 아니라 다음 순서의 독립 gate다.

#### Phase 0A — 현재 코어 연결과 안전성

- 현재 6개 Shopify adapter의 전 variant 계약
- Le Cashmere 제거와 PLUSH’MERE target registry 반영
- 통합 `AnalysisInput`과 실제 model payload manifest/hash test
- 상품 집계·steady·coverage·failure의 분석 입력 연결
- 공통 evidence/provenance와 typed Claim/FactRef
- 현재 NAVER client의 상대 신호 계약
- 빈 데이터·LLM 실패 deterministic fallback HTML
- action evidence의 Markdown/HTML 노출
- 통화 분리/환산 invariant
- empty/partial/full report·pipeline fixture tests

#### Phase 0B — 상품 source 확장

- Source Registry와 policy validator
- 비-Shopify 5개 target adapter
- exact-brand·eligibility·pagination 검증
- fixture CI와 opt-in live smoke

#### Phase 0C — 패션 evidence와 v2 report

- allowlisted RSS·sitemap·정적 HTML editorial collector
- runway observation collector
- Tavily 런타임 경로 제거
- trend adoption과 independent publisher 판정
- 기존 7-section golden을 보존하는 v2 Report Quality Contract

제외:

- Discord
- FastAPI
- 복잡한 SQLite 상태머신
- 다중 worker
- cron

### Phase 1 — 최소 Hermes 제품

포함:

- 저장소 root `AGENTS.md`
- 단일 `md-trend-report` skill
- Hermes Desktop 자연어 요청
- 계획 제안·수정·승인
- 승인자의 명시적 응답과 plan hash를 `approval.json`에 기록
- Python CLI 단계 호출
- run-scoped 파일 저장
- 결과 파일 전달

### Phase 2 — Discord와 내구성

포함:

- Hermes Discord Gateway
- run별 Discord thread
- 사용자·서버·채널 allowlist
- SQLite 요청·계획·실행·근거·주장·보고서 이력
- 취소·재실행
- stale 승인 차단
- Hermes 재시작 복구

### Phase 3 — 운영 확장

필요할 때만 포함:

- FastAPI 내부 API
- collector/browser worker 분리
- lease·heartbeat
- 다중 동시 실행
- Docker 네트워크 격리
- cron과 실패 알림

---

## 7. 목표 아키텍처

```text
Hermes Desktop / Discord Gateway
                │
                ▼
      Hermes md-trend-report skill
                │
        plan / approve / audit
                │
                ▼
       Python application commands
                │
  ┌─────────────┼───────────────┐
  ▼             ▼               ▼
Product       NAVER         Editorial/Runway
Collectors    Clients       Collectors
  │             │               │
  └─────────────┼───────────────┘
                ▼
      Normalization + Aggregation
                ▼
           AnalysisInput
                ▼
   Hermes Researcher / Analyst / Editor
                ▼
     Output Validation + Contradiction Audit
                ▼
  Deterministic Markdown / HTML Renderer
                ▼
       Run Bundle / SQLite / Delivery
```

### 7.1 초기 Python 명령 경계

Phase 1의 목표 명령 구조:

```text
python -m md_trend_agent request-validate REQUEST.json
python -m md_trend_agent plan-validate PLAN.json
python -m md_trend_agent collect PLAN.json --run-dir RUN_DIR
python -m md_trend_agent build-analysis-input --run-dir RUN_DIR
python -m md_trend_agent validate-analysis OUTPUT.json --run-dir RUN_DIR
python -m md_trend_agent render --run-dir RUN_DIR
```

현재 `python -m poc.run`은 Phase 0의 임시 통합 entry point다. 새 CLI가 검증되기 전 제거하지 않는다.

### 7.2 Hermes project context

초기에는 저장소 root `AGENTS.md` 하나를 사용한다. Hermes는 시작 시 `.hermes.md` → `AGENTS.md` → `CLAUDE.md` → `.cursorrules` 순서에서 첫 context type만 선택하므로 root `AGENTS.md`를 추가하면 기존 `CLAUDE.md`는 시작 context로 자동 병합되지 않는다. 구현 전에 `CLAUDE.md`의 유효한 프로젝트 규칙을 `AGENTS.md`로 이관한다.

Hermes는 도구가 하위 디렉터리에 접근할 때 그 경로의 `AGENTS.md` 또는 `CLAUDE.md`를 점진적으로 발견할 수 있다. 이 기능은 세부 패키지 규칙에만 사용하고 root 규칙을 대체하지 않는다.

`AGENTS.md`에는 다음만 둔다.

- 허용 명령
- 데이터·보안 정책
- 테스트 명령
- 산출물 경로
- 실패 시 행동
- `md-trend-report` skill 로드 조건

시작 context 기본 제한 20,000자를 넘는 도메인 절차는 skill로 분리한다.

---

## 8. 핵심 데이터 계약

모든 계약은 Pydantic 모델과 version field를 가진다. LLM 입출력은 JSON Schema로 검증한다.

### 8.1 AnalysisRequest

```yaml
schema_version: "2.0"
request_id: uuid
category: string
focus: string|null
market: KR
season: string|null
target:
  gender: female
  requested_age: 25-39
price_range:
  currency: KRW
  min: 200000
  max: 700000
window:
  start: date
  end: date
brand_set: cashmere-reference
focus_dimensions: [item, color, material, silhouette, detail, price]
user_keywords: [string]
user_source_urls: [https-url]
```

### 8.2 CollectionPlan

```yaml
schema_version: "2.0"
plan_id: uuid
request_id: uuid
plan_version: 1
plan_hash: sha256
questions:
  - question_id: string
    text: string
    required_dimensions: [item|color|material|silhouette|detail|price|demand|trend]
brands:
  - brand_id: string
    status: target|excluded
    source_ids: [string]
product_sources:
  - source_id: string
    role: primary|fallback
    criticality: required|optional
    max_pages: int|null
    max_products: int|null
naver_tasks:
  - task_id: string
    api: search_trend|shopping_category|shopping_keyword|blog_search
    request_group_id: string
    criticality: required|optional
    no_observation_allowed: bool
editorial_feeds:
  - source_id: string
    max_articles: int
    criticality: required|optional
    no_observation_allowed: bool
article_filters:
  include_keywords: [string]
  exclude_categories: [string]
collection_budget:
  max_article_fetches: int
  max_dynamic_fetches: int
  max_browser_actions: int
  deadline_seconds: int
stop_conditions: [string]
policy_result: approved|rejected
```

승인 이후 `plan_version`과 `plan_hash`는 불변이다. 수정은 새 version을 만든다.

#### 8.2.1 ApprovalRecord

```yaml
approval_id: uuid
request_id: uuid
run_id: uuid
plan_id: uuid
plan_version: int
plan_hash: sha256
status: approved|rejected|cancelled
approved_by: string
channel_type: desktop|discord
channel_id: string
approved_at: datetime
explicit_user_text_hash: sha256
supersedes_approval_id: uuid|null
```

수집 command는 `approval.json`의 plan ID/version/hash가 실행할 `plan.json`과 모두 일치하고 status가 approved일 때만 시작한다. plan이 수정되면 기존 approval은 stale이며 재사용할 수 없다. Hermes의 내부 판단이나 policy validator의 `policy_result`는 사용자 승인을 대신하지 않는다.

### 8.3 SourceRegistryEntry

```yaml
source_id: stable string
entity_type: brand|publisher|fashion_week|public_api
entity_name: string
owner_group: string|null
expected_brand_names: [string]
brand_match_mode: source_brand_field|official_single_brand_store|validated_product_metadata|null
url: https://...
source_type: official_store|official_brand_page|domestic_retailer|global_retailer|rss|sitemap|editorial_index|runway_index|public_api
market: KR|US|GB|EU|GLOBAL
currency: KRW|USD|GBP|EUR|null
access_mode: shopify_api|rest_api|static_html|json_ld|hydration|xhr|dynamic_browser|rss|sitemap
api_documentation_url: https-url|null
api_auth: none|issued_free_key|session_cookie|signed_token
free_quota: string|null
priority: 1
status: active|reference_only|excluded|temporarily_failed
robots_policy: obey
robots_url: https://.../robots.txt
robots_checked_at: datetime|null
robots_content_hash: sha256|null
allowed_paths: [string]
disallowed_paths: [string]
crawl_delay_seconds: decimal|null
terms_review_status: public_fetch_reviewed|restricted|manual_review_required
collection_mode: automated_poc|automated_production|manual_only|blocked
retention_mode: none|derived_only|contract_allowed
terms_url: https-url|null
terms_checked_at: datetime|null
access_status: public_full|public_partial|index_only|blocked|paywalled|unknown
policy_expires_at: datetime|null
cache_ttl_seconds: int
incremental_key: lastmod|published_at|content_hash|none
requires_login: false
expected_count: int|null
last_checked_at: datetime|null
last_status: string|null
notes: string|null
adapter_version: string
fixture_path: string
fixture_hash: sha256
last_live_checked_at: datetime|null
live_check_status: passing|drifted|blocked|unknown
```

`expected_count`는 조사 참고값이다. 실행 커버리지 계산은 실제 `collected_count`를 사용한다. POC에서는 `public_fetch_reviewed + automated_poc` source를 자동 fetch할 수 있으며 production contract를 필수 선행조건으로 두지 않는다. `restricted`, `requires_login=true`, `blocked`, `paywalled` source는 자동 fetch 계획을 통과할 수 없다. `manual_review_required` 또는 `manual_only` source는 수동 관찰 task로 전환한다. `public_fetch_reviewed`는 공개 접근, robots와 명시적 제한을 검토했다는 POC 정책 판단이며 법적 권리 보장을 의미하지 않는다. robots와 약관 snapshot이 만료됐거나 hash가 변경되면 재검사하되, 단순 미확인을 영구 금지로 간주하지 않고 bounded probe 또는 manual review 중 하나를 계획에 명시한다. 수집 중 로그인·구독·CAPTCHA가 나타나면 즉시 중단하고 access status를 갱신한다.

`issued_free_key`는 NAVER/KEXIM처럼 발급된 무료 quota API를 의미하며 허용된다. quota를 넘기면 유료 전환하지 않고 cache 사용 또는 부분 실패로 종료한다. `session_cookie`, `signed_token`, mutation endpoint, endpoint brute force는 금지한다. XHR/hydration은 정상 공개 UI가 호출하는 read-only endpoint이고 registry review가 완료된 경우만 허용한다. robots, 약관, endpoint 정책이 충돌하면 가장 엄격한 조건을 적용한다.

Source를 `active`로 승격하려면 adapter fixture hash, exact-brand/eligibility, 필수 field schema, pagination 종료, URL policy test가 통과해야 한다. 필수 상품 field는 source/brand/title/canonical URL, 고유 product·observation·evidence ID, variant ID·native price·availability이며 지원하지 않는 field는 null과 `missing_fields`로 명시한다. fixture는 target/non-target, eligible/ineligible, 다중 page, 다중 variant, sold-out과 sale 사례를 포함한다. live smoke는 CI와 분리하며 `last_live_checked_at`이 기본 30일보다 오래됐거나 `drifted`면 계획에 경고하고 우선 fixture 상태와 실제 실패를 구분해 기록한다. live drift 자체는 코드 CI 실패가 아니지만 해당 run source는 성공으로 오판하지 않는다.

#### 8.3.1 Scrapling과 수동 fallback

공식 저장소 `https://github.com/d4vinci/Scrapling`의 고정 버전을 POC 기본 scraper로 사용한다.

```text
공개 API/read-only endpoint
→ Scrapling Fetcher
→ Scrapling DynamicFetcher + allowlisted capture_xhr
→ 제한적 Browser fallback
→ ManualObservationTask
→ validated EvidenceRef
```

`solve_cloudflare=False`, proxy rotation 비활성, spider의 `robots_txt_obey=True`, `follow_redirects="safe"`, `max_redirects=3`을 강제한다. 반복 429, CAPTCHA, WAF, 로그인, paywall과 명시적 block은 중단 신호다. Shopify는 collection 중복 요청을 만드는 `ShopifySpider`를 기본값으로 쓰지 않고 공개 `/products.json?page=N&limit=250` bounded pagination을 우선한다.

수동 관찰은 `task_id`, `run_id`, `plan_hash`, `source_id`, canonical URL, `observed_at`, `observed_by`, `reviewed_by`, 구조화 사실, 짧은 excerpt, provenance method와 validation status를 가진다. 자동 실패 outcome은 삭제하지 않고 자동·수동·미관찰 coverage를 분리한다.

### 8.4 ProductRecord

```yaml
schema_version: "2.0"
product_id: stable string
source_product_id: string|null
observation_id: uuid
evidence_id: PRD-*
run_id: uuid
brand: string
source_id: string
source_url: https://...
canonical_url: https://...
market: string
collected_at: datetime
published_at: datetime|null
published_at_source: structured|page_text|unknown
title: string
product_type_raw: string|null
category_raw: string|null
tags_raw: [string]
product_status: active|draft|archived|unknown
eligibility_status: eligible|ineligible|unknown
eligibility_reasons: [string]
eligibility_rule_version: string
item_normalized: string|null
colors_raw: [string]
color_families: [string]
materials_raw: [string]
materials_normalized: [string]
silhouettes: [string]
details: [string]
variants:
  - variant_id: string
    title: string|null
    price_native: decimal|null
    compare_at_price_native: decimal|null
    available: bool|null
price:
  currency_native: string|null
  min_native: decimal|null
  max_native: decimal|null
  min_krw: decimal|null
  max_krw: decimal|null
  fx_source: KEXIM_AP01|null
  fx_rate: decimal|null
  fx_requested_date: date|null
  fx_date: date|null
  fx_fallback: bool
sale:
  any_variant_on_sale: bool|null
  sale_variant_ratio: decimal|null
availability:
  any_available: bool|null
  all_sold_out: bool|null
field_provenance:
  item: structured|rule|llm_verified|missing
  color: structured|rule|llm_verified|missing
  material: structured|rule|llm_verified|missing
  silhouette: structured|rule|llm_verified|missing
missing_fields: [item|color|material|silhouette|price|availability]
extractor_version: string
content_hash: sha256
```

첫 variant만 상품 전체 가격과 세일 상태로 사용하지 않는다.

불변 조건:

- `product_id`는 `source_id + source_product_id`, 없으면 정규화 canonical URL hash다. cross-source global identity로 사용하지 않는다.
- canonical URL은 fragment, tracking query, locale-only query를 제거한 HTTPS URL이다. source별 allowlist query만 남긴다.
- `(run_id, observation_id)`, `(run_id, evidence_id)`는 유일하며 `EvidenceRef.record_id=observation_id`다.
- variant ID는 ProductRecord 안에서 유일하며 빈 문자열을 허용하지 않는다.
- 가격은 finite, 0 이상이고 min ≤ max다. native amount와 currency는 all-or-none다.
- `compare_at_price_native > price_native`인 variant만 sale이다. sale ratio는 0~1이다.
- `any_available = any(variant.available is True)`, 모든 variant가 명시적으로 false일 때만 `all_sold_out=true`다.
- KRW 가격이 있으면 FX source/date/rate가 모두 존재한다. `fx_fallback=true`이면 요청 기준일과 실제 사용 기준일을 모두 기록한다.
- raw/normalized list는 trim 후 빈 문자열과 중복을 허용하지 않는다.
- datetime은 timezone-aware다. `published_at_source=unknown`이면 published_at은 null이다.
- `content_hash`는 수집 시각을 제외한 정규화 의미 필드와 extractor version을 canonical JSON으로 직렬화해 계산한다.
- 분석 집계와 source 성공 판정에는 `eligibility_status=eligible`, `product_status in {active, unknown}`만 포함한다. unknown/ineligible은 관찰·실패 진단에는 보존하지만 상품 분석 분모와 성공 건수에서 제외한다.

`observation_id`는 run별 관찰을 식별하며 상품 내용이 바뀌어도 기존 관찰을 덮어쓰지 않는다. LLM 추출 필드는 원문 substring 검증을 통과한 경우에만 `llm_verified`가 된다.

### 8.5 EditorialEvidence

```yaml
schema_version: "2.0"
evidence_id: EDT-*
run_id: uuid
source_id: string
publisher: string
publisher_owner_group: string|null
source_type: official|runway|editorial|commercial_editorial
canonical_url: https://...
canonical_work_hash: sha256
syndication_parent_url: https-url|null
title: string
author: string|null
published_at: datetime|null
retrieved_at: datetime
access_status: public_full|public_partial|index_only|video_only|blocked|paywalled
sponsored: true|false|unknown
affiliate: true|false|unknown
season: string|null
city: string|null
brands: [string]
categories: [string]
materials: [string]
colors: [string]
silhouettes: [string]
items: [string]
trend_claims: [string]
short_excerpt: string|null
image_urls: [https-url]
image_usage: link_only|embed_allowed|unknown
image_credit: string|null
evidence_tier: A|B|C
content_hash: sha256
```

원문 전체를 보고서에 재배포하지 않는다. 분석에 필요한 최소 발췌와 URL만 저장·노출한다. `short_excerpt`는 공백 정규화 후 최대 1,000자, 보고서 직접 노출은 evidence당 최대 300자로 제한한다. 이 한도도 source 약관보다 우선하지 않는다.

claim evidence에는 `public_full` 또는 claim을 실제 공개 excerpt에서 검증한 `public_partial`만 사용할 수 있다. `index_only`, `video_only`, `blocked`, `paywalled`는 discovery/limitation metadata이며 claim 근거가 아니다. 독립 publisher 수는 `owner_group`과 `canonical_work_hash`가 모두 알려져 있고 서로 다른 항목만 센다. owner group이 unknown이면 독립 publisher threshold에는 포함하지 않는다. 동일 보도자료·syndication 재게시물은 하나의 work로 계산한다.

Runway 관측은 일반 EditorialEvidence만으로 대체하지 않는다.

```yaml
RunwayObservation:
  evidence_id: RUN-*
  run_id: uuid
  source_id: string
  fashion_week: string
  designer_or_brand: string
  collection: string
  season: string
  city: string|null
  look_or_segment: string|null
  observation_method: official_caption|public_review|human_verified_visual
  observed_at: datetime
  canonical_url: https-url
  observed_facts: [string]
  observer: string
  content_hash: sha256
```

`human_verified_visual`은 자동 이미지 인식만으로 생성하지 않으며 관측자와 원본 locator가 있어야 Tier A다.

### 8.6 EvidenceRef

`evidence_ids`가 공통으로 참조하는 catalog 항목이다. 원본 record 전체를 복제하지 않고 검증 가능한 locator를 가진다.

```yaml
evidence_id: PRD-*|AGG-*|NAV-*|EDT-*|RUN-*|STD-*
run_id: uuid
plan_hash: sha256
kind: product|aggregate|naver_signal|editorial|runway|steady
source_id: string
evidence_tier: A|B|C
canonical_url: https://...|null
observed_at: datetime
summary: string
claim_scopes: [item, color, material, silhouette, price, demand, trend, availability]
record_locator:
  relative_path: string
  record_id: string
content_hash: sha256
input_manifest_hash: sha256|null
input_count: int|null
parent_evidence_ids: [string]
calculation_method: string|null
code_version: string
alias_of: string|null
```

ID는 run 안에서 유일하고 불변이며 claim은 같은 `run_id`와 `plan_hash`의 evidence만 참조한다. namespace와 원본 record의 정규화 hash로 결정적으로 생성한다. 동일 run에서 URL 또는 content hash가 중복되면 하나를 canonical evidence로 정하고 나머지는 `alias_of`로 연결해 독립 근거 수에 중복 계산하지 않는다. 같은 원본을 재수집해 내용이 바뀌면 새 observation과 새 evidence ID를 만든다. `AGG-*`는 집계 산출물과 전체 입력 observation manifest hash, parent IDs, 계산식·code version을 연결하며 Python auditor가 원 ProductRecord에서 재계산할 수 있어야 한다.

`stale evidence`는 현재 analysis의 run_id 또는 승인 plan_hash와 다르거나, manifest에 존재하지 않거나, canonical evidence가 무효화된 ID다. auditor는 이를 hard failure로 거부한다.

### 8.7 CoverageMetrics

```yaml
brands_targeted: int
brands_collected: int
brands_failed: int
brands_excluded: int
brands_reference_only: int
sources_attempted: int
sources_succeeded: int
products_collected: int
field_coverage:
  price: CoverageValue
  color: CoverageValue
  material: CoverageValue
  silhouette: CoverageValue
  item: CoverageValue
editorial_sources_targeted: int
editorial_sources_succeeded: int
collection_failures: [CollectionFailure]
freshness_cutoff: datetime
```

분모 규칙:

- `brands_targeted`: 승인 plan의 `status=target`; excluded와 reference-only 제외
- `brands_collected`: 유효 `ProductRecord`가 1개 이상인 target brand
- `brands_failed`: `brands_targeted - brands_collected`
- `sources_attempted`: 실제 네트워크 요청을 시작한 source
- `sources_succeeded`: primary 또는 fallback 여부와 무관하게 해당 source의 성공 판정을 통과한 source
- `products_collected`: dedupe 후 `eligibility_status=eligible`인 canonical ProductRecord observation 수
- product field coverage: eligible ProductRecord를 분모로 하며 다값 field는 유효 값이 1개 이상이면 covered, 빈 list는 observed-empty가 아니라 missing
- editorial source coverage: 승인 plan에 선택된 publisher 중 분석 기간에 적합 기사 1개 이상을 수집한 publisher
- freshness: 상품은 `collected_at`, 기사/runway는 `published_at`이 있으면 published_at, 없으면 `retrieved_at`; cutoff와 timezone을 함께 기록

각 값은 numerator, denominator, ratio를 함께 직렬화한다. denominator가 0이면 ratio는 `null`이며 0%로 표현하지 않는다.

### 8.8 AnalysisInput

```yaml
schema_version: "2.0"
request: AnalysisRequest
approved_plan: CollectionPlan
product_record_manifest:
  relative_path: string
  count: int
  content_hash: sha256
brand_aggregates: [BrandAggregate]
market_rollups: MarketRollup
source_coverage: CoverageMetrics
field_coverage: {string: CoverageValue}
collection_failures: [CollectionFailure]
naver_signals: [NaverSignal]
editorial_evidence: [EditorialEvidence]
runway_evidence: [RunwayObservation]
steady_signals: [SteadySignal]
evidence_catalog: [EvidenceRef]
currency_context: CurrencyContext
```

전체 `ProductRecord` 수천 건은 LLM context에 직접 넣지 않는다. Python이 계산한 브랜드 집계·시장 롤업과 대표 관찰 evidence만 전달하고, 전체 record는 run-relative path와 hash로 참조한다. 감사 또는 보완 질문에 필요한 record만 제한적으로 조회한다.

`evidence_catalog`는 claim에서 참조 가능한 모든 근거의 최소 메타데이터를 합친다.

```text
PRD-*  상품 관찰
AGG-*  상품 관찰 집계와 입력 manifest
NAV-*  NAVER 요청 내 상대 신호
EDT-*  에디토리얼 기사
RUN-*  런웨이 관찰
STD-*  스테디셀러 관찰
```

분석 모델이 보지 못한 데이터는 분석 문장에서 확정적으로 언급할 수 없다. `evidence_ids`는 catalog에 존재하고 claim scope와 일치해야 한다.

관련 named contract:

```yaml
CoverageValue:
  numerator: int
  denominator: int
  ratio: decimal|null

CollectionFailure:
  failure_id: string
  source_id: string
  stage: discovery|fetch|extract|normalize|analyze|render
  failure_code: string
  retry_count: int
  occurred_at: datetime
  message: string

AggregateMetric:
  value: object
  method: string
  evidence_id: AGG-*

BrandAggregate:
  brand: string
  source_ids: [string]
  product_count: int
  coverage: {string: CoverageValue}
  items: AggregateMetric
  colors_family: AggregateMetric
  colors_raw: AggregateMetric
  price_native: AggregateMetric
  price_krw: AggregateMetric
  sale: AggregateMetric
  materials: AggregateMetric
  silhouettes: AggregateMetric
  newness: AggregateMetric

MarketRollup:
  brands_included: [string]
  product_count: int
  coverage: {string: CoverageValue}
  items: AggregateMetric
  colors: AggregateMetric
  materials: AggregateMetric
  silhouettes: AggregateMetric
  prices: AggregateMetric
  gaps: AggregateMetric

NaverSignal:
  evidence_id: NAV-*
  api: search_trend|shopping_category|shopping_keyword|blog_search
  request_group_id: string
  request_hash: sha256
  requested_segment: string
  observed_segment: string
  coverage_mismatch: bool
  normalization_scope: string
  series: [{period: date, ratio: decimal}]

SteadySignal:
  evidence_id: STD-*
  brand: string
  source_id: string
  current_observation_ids: [uuid]
  prior_observation_ids: [uuid]
  window_start: date
  window_end: date
  rule_version: string
  signal: persistent|new|disappeared|unknown
  content_hash: sha256

CurrencyContext:
  target_currency: KRW
  fx_source: KEXIM_AP01|null
  fx_date: date|null
  fallback_used: bool
  rates_hash: sha256|null
```

### 8.9 Claim과 AnalysisOutput

주요 서술 단위는 공통 `Claim`을 사용한다.

```yaml
FactRef:
  fact_id: string
  subject: string
  metric: product_count|share|price|min_price|max_price|ratio|change|rank|presence|absence
  value_number: decimal|null
  value_text: string|null
  unit: count|percent|ratio|KRW|USD|GBP|EUR|boolean|string
  comparator: eq|gt|gte|lt|lte|between|increased|decreased|present|absent
  period_start: date|null
  period_end: date|null
  evidence_ids: [string]

Claim:
  claim_id: string
  claim_type: summary|trend|brand_signature|gap|opportunity
  title: string|null
  statement: string
  scope:
    brands: [string]
    market: string|null
    season: string|null
    window_start: date|null
    window_end: date|null
  facts: [FactRef]
  evidence_ids: [string] # supported이면 min_items=1, unique
  status: supported|hypothesis|insufficient
  confidence: high|medium|low
  confidence_reasons: [string]
  rule_version: string
```

```yaml
AnalysisOutput:
  schema_version: "2.0"
  executive_summary: [Claim]
  trends:
    - claim: Claim
      stage: rising|mainstream|saturated|slowing|hypothesis
  brand_signatures: [Claim]
  gaps: [Claim]
  opportunities: [Claim]
  actions:
    - action_id: string
      priority: high|medium|low
      action: string
      rationale: string
      facts: [FactRef]
      evidence_ids: [string]   # min_items=1, unique
      related_claim_ids: [string]
      risks: [string]
  limitations:
    - limitation_code: string
      statement: string
      affected_claim_ids: [string]
      affected_source_ids: [string]
```

검증 규칙:

- `supported` claim은 evidence가 최소 1개다.
- `hypothesis`는 evidence를 가질 수 있지만 보고서에서 확정 표현을 사용할 수 없다.
- `insufficient`는 executive summary, MD action, 확정 trend에 노출하지 않고 limitation으로 렌더링한다.
- 모든 evidence ID와 related claim ID는 실제 catalog/output에 존재해야 한다.
- executive summary, brand signature, gap, opportunity에도 evidence를 강제한다.
- statement/rationale의 수치·가격·비율·기간 표현은 동일 값을 가진 `FactRef`가 있어야 하며 Python auditor가 evidence/aggregate에서 재계산한다.
- 정성적 “관련 있음”은 자동 통과 조건으로 삼지 않는다. schema·run·scope·FactRef 검사는 blocking, 의미 관련성은 Hermes Auditor와 MD 수동 평가가 판정한다.
- 배열 원소의 enum, 최소·최대 개수, 중복 금지는 JSON Schema와 Pydantic에서 동일하게 검증한다.

---

## 9. 상품 Source Registry

기본 세트 이름은 `cashmere-reference`다. Le Cashmere는 정확한 활성 상품 소스를 확보하지 못해 제외한다.

### 9.1 대상 브랜드 11개

| 브랜드 | 1차 소스 | fallback | 방식 |
|---|---|---|---|
| Guest in Residence | 공식몰 | REVOLVE, NET-A-PORTER KR | Shopify API |
| Extreme Cashmere | 공식몰 | Mytheresa, FARFETCH, SSF | Shopify API |
| &Daughter | 공식몰 | NET-A-PORTER, SSENSE KR | Shopify API |
| Lisa Yang | 공식몰 | FARFETCH, Mytheresa KR | Shopify API |
| ARCH4 | 공식몰 | FARFETCH, W CONCEPT exact brand | Shopify API |
| Iris Von Arnim | Breuninger | 공식몰, FARFETCH KR | JSON-LD + pagination/API |
| LE17 SEPTEMBRE | SSF SHOP | 공식몰 | 정적 상품 카드 + pagination |
| Quince | 공식몰 | 없음 | Next.js hydration + 공개 상품 API |
| Cashmere in Love | 공식몰 | FARFETCH KR | Shopify API |
| COS | SSG.COM | 공식몰, Nordstrom | 정적 상품 카드 + pagination |
| PLUSH’MERE | 코오롱몰 | 공식 Instagram은 reference-only | Next.js data/공개 상품 endpoint |

이 표는 2026-07-22 smoke test로 확인한 **adapter 후보**다. HTTP 접근·구조 단서를 확인했지만 11개 모두의 전량 pagination, 브랜드 정확도, 필드 완전성을 아직 보장하지 않는다. 각 adapter는 fixture와 opt-in live smoke 수용 기준을 통과해야 `status=active`가 된다.

### 9.2 제외 브랜드

```yaml
brand: Le Cashmere
status: excluded
reason: 정확한 활성 상품 소스 미확보
```

W CONCEPT의 `르캐시미어` 키워드 검색 결과는 다른 `르*` 브랜드를 포함한다. 브랜드 exact match가 검증되지 않으므로 사용하지 않는다.

### 9.3 소스 선택 규칙

1. 공식몰 또는 공식 브랜드관
2. 국내 리테일러
3. 한국 구매 가능한 글로벌 리테일러
4. 기타 해외 리테일러
5. reference-only

공식몰이 기술적으로 수집 불가능하거나 활성 상품이 없으면 더 낮은 우선순위의 정확한 브랜드 리테일러를 사용한다.

동일 상품이 여러 소스에 있으면 URL, 브랜드, 정규화 상품명, 이미지 fingerprint 없이 사용 가능한 SKU·style code로 중복 후보를 만든다. 확정 불가능하면 소스별 관찰을 유지하고 cross-source duplicate 가능성을 표시한다.

---

## 10. 상품 수집 사다리

### 10.1 Shopify

공식 `/products.json?limit=250&page=N`을 빈 페이지까지 순회한다.

요구사항:

- 페이지네이션 필수
- 모든 variant 보존
- 최소가·최대가 계산
- 일부 variant 세일과 전체 세일 구분
- 일부 재고와 전체 품절 구분
- native currency 보존
- rate limit과 429 기록

Scrapling의 기본 `ShopifySpider`는 사용하지 않는다. 2026-07-22 Guest in Residence smoke test에서 814개 요청 중 712개가 429였고, collection별 중복 상품 요청이 발생했다. 필요하면 Scrapling `FetcherSession`만 직접 `/products.json` 호출에 사용한다.

### 10.2 비-Shopify

수집 순서:

1. 공개 플랫폼 API 또는 XHR
2. sitemap product URL
3. 정적 HTML product card
4. JSON-LD `Product`
5. `__NEXT_DATA__`, React Server Component, `__NUXT__` 등 hydration data
6. Scrapling `DynamicFetcher`와 `capture_xhr`
7. 제한적 browser action
8. 실패 기록

### 10.3 Scrapling 역할

사용:

- `Fetcher`/`FetcherSession` 정적 수집
- 안전한 redirect
- CSS/XPath 선택
- JSON-LD·hydration parsing
- `DynamicFetcher` JavaScript 렌더링
- `capture_xhr` 공개 상품 endpoint 발견
- explicit selector 실패 시 adaptive selector 보조

금지:

- Cloudflare challenge 해결
- CAPTCHA 우회
- proxy rotation
- 차단 회피 목적 `StealthyFetcher`
- 로그인 세션 수집

Adaptive selector는 복구 보조다. 주 수집은 명시적 selector/API와 스키마 검증을 사용한다.

### 10.4 성공 판정

브랜드 소스 성공:

- HTTP 성공만으로 판정하지 않는다.
- 브랜드 exact match가 확인된다.
- 유효 상품 record가 1개 이상이다.
- 필수 identity 필드가 존재한다.
- collected count와 pagination 종료 근거가 있다.

HTTP 200이지만 상품 0개면 `empty_source`다. 키워드 검색 오탐이면 `brand_mismatch`다.

---

## 11. 패션·에디토리얼 채널

### 11.1 채널 목록

| 채널 | 발견 경로 | 접근 상태 | 주 역할 |
|---|---|---|---|
| Vogue Runway | RSS, 월별 sitemap, season index | `public_partial` | 시즌·브랜드·look·리뷰 발췌 |
| Fashionista | `https://fashionista.com/feed` | `public_full` | 런웨이·산업·스타일 해석 |
| Highsnobiety | `/feed/`, content/news sitemap | `public_full` | 스트리트·남성·문화 확산 |
| Hypebeast | `/feed` | `public_full` | 협업·드롭·제품 문화 |
| FashionNetwork | 공개 뉴스·카테고리 | `public_full` | 산업·리테일·정량 전망 |
| Who What Wear | `/rss` | `public_full` | 소비자 스타일·컬러·아이템 |
| NOWFASHION | `/feed/`, collection index | `public_full` | runway look·일정·시즌 |
| CFDA/공식 FW | 공식 일정·뉴스 | `public_full` | 공식 일정·참가 브랜드 |
| SHOWstudio | collection index | `video_only` 또는 `public_full` press release | 비평 영상·press release·catwalk |

접근 상태는 실행마다 갱신한다. 무료 접근이 영구 보장된다고 가정하지 않는다.

### 11.2 Vogue Runway 제한

Vogue Runway는 전체 리뷰 텍스트의 무제한 소스로 사용하지 않는다.

허용:

- season·city·brand·collection metadata
- 공개된 리뷰 발췌
- 공개 look 번호와 원문 링크
- image URL과 credit metadata

금지:

- 구독 본문 우회
- AI crawler 차단 회피
- 전체 이미지 대량 재배포

### 11.3 발견 전략

RSS와 sitemap을 우선 사용한다. 홈 전체를 반복 크롤링하지 않는다.

검증된 feed 규모는 2026-07-22 smoke test 기준이다.

- Vogue RSS: 30개
- Fashionista RSS: 50개
- Highsnobiety RSS: 16개
- Hypebeast RSS: 20개
- Who What Wear RSS: 50개
- NOWFASHION RSS: 10개

이 수는 성공 기준이 아닌 운영 참고값이다.

### 11.4 기사 필터

기본 키워드:

```text
cashmere, knitwear, wool, alpaca, merino,
cardigan, sweater, layering, texture, craft,
soft tailoring, natural fiber, fall, winter, pre-fall
```

브랜드명, 시즌, 컬러, 소재, 아이템, 실루엣 용어를 추가한다. Sponsored, affiliate, job listing, beauty-only 콘텐츠는 별도 분류하거나 제외한다.

### 11.5 편집 관심과 수요 구분

기사 언급량은 editorial attention이다. 판매량이나 소비자 수요로 표현하지 않는다. 국내 수요 판단은 NAVER와 리테일 실측을 함께 사용한다.

---

## 12. NAVER 수요 계층

NAVER API HUB만 사용한다.

### 12.1 Search Trend

- 25~39세: `ages=["4", "5", "6"]`
- 캐시미어 니치 수요의 주 정량 축
- ratio는 요청 내 상대값
- 서로 다른 요청의 ratio를 절대량처럼 비교하지 않는다

### 12.2 Shopping Insight categories

- 20~39세: `ages=["20", "30"]`
- 요청 segment 25~39와 정확히 일치하지 않음
- `coverage_mismatch=true` 의무 표시

### 12.3 Shopping Insight keywords

- gender/ages filter를 제거한 broad keyword 보조 신호
- 세부 캐시미어 키워드는 집계 임계 미달로 빈 결과 가능
- 빈 결과를 “수요 없음”으로 해석하지 않는다

### 12.4 NAVER Blog Search

- 한국 소비자 정성 언어
- 컬러 조합, 코디, 간절기, 브랜드 언급
- URL과 발췌가 있어 editorial evidence와 같은 evidence ID 대상
- 광고성·체험단 신호를 분류한다

---

## 13. 정규화와 집계

### 13.1 통화

환율 적용 전에는 서로 다른 통화를 한 숫자 축으로 정렬하지 않는다.

저장:

- native price
- native currency
- KRW normalized price
- FX 기준일
- fallback 여부

KEXIM AP01 캐시를 사용한다. 실패·주말·공휴일에는 직전 유효 영업일 값을 사용하고 보고서에 표시한다.

### 13.2 컬러

고정 계열:

1. 뉴트럴
2. 베이지·카멜·브라운
3. 블루·네이비
4. 그린
5. 레드·핑크
6. 옐로·오렌지
7. 퍼플
8. 멀티·패턴

raw color와 family를 모두 저장한다. 새 컬러명 LLM 분류는 원본 substring 검증과 수동 교정 가능 캐시를 가진다.

### 13.3 소재·아이템·실루엣

필드별 순서:

1. 구조화 데이터
2. 명시적 사전/규칙
3. LLM 추출
4. 원본 substring 검증
5. 미확인

가격은 LLM이 추출·계산하지 않는다.

### 13.4 브랜드 집계

브랜드별 최소 출력:

```text
source
coverage
currency/fx
items
colors_family
colors_raw
price_native
price_krw
price_band
sale
materials
silhouettes
newness
failures
```

### 13.5 시장 롤업

- 브랜드 커버리지
- 상품 수
- 핵심 아이템
- 컬러 family와 raw color
- 가격 분포
- 소재
- 실루엣
- 신상
- 공급 공백
- 실패와 제외

### 13.6 시간과 재현성

- `run_started_at`, `collected_at`, `observed_at`은 timezone-aware UTC다.
- 사용자에게 표시하는 business date와 “최근 8주” 기준일은 run 생성 시 고정한 `analysis_as_of_date`(Asia/Seoul)다.
- `window.start/end`는 계획 승인 전에 절대 날짜로 확정하고 실행 중 자정을 지나도 바꾸지 않는다.
- renderer는 `date.today()`를 호출하지 않고 run bundle의 고정 시각만 사용한다.
- 재렌더링은 같은 bundle에서 동일 의미 결과를 생성한다.
- manifest는 source registry hash, extractor version, prompt/skill version, color/material normalization dictionary hash, FX rates hash, timezone, analysis_as_of_date를 기록한다.
- 실시간 source 변경으로 완전한 byte 동일 재수집은 보장하지 않지만 동일 run bundle의 집계·감사·렌더링은 결정적이어야 한다.

---

## 14. Evidence 정책

### 14.1 Tier

Tier A:

- 공식 상품 데이터
- 공식 브랜드 발표
- 공식 fashion week 일정
- 직접 runway 관측
- NAVER 정량 신호

Tier B:

- Vogue, Fashionista, Highsnobiety, Hypebeast, FashionNetwork 편집 기사

Tier C:

- Who What Wear 쇼핑 기사
- affiliate·sponsored 콘텐츠
- retailer editorial
- 단일 간접 언급

현재 `poc/analyze.py`의 숫자 tier(`1=업계지`, `2=에디토리얼`, `3=공식몰`, `4=저권위`)는 전환기 형식이다. Phase 0에서 A/B/C와 `source_type`으로 마이그레이션하며 두 체계를 한 run에서 혼용하지 않는다.

NAVER 정량 신호에는 `NAV-*` ID를 부여할 수 있지만 다음 범위에서만 근거로 사용한다. 이는 NAVER signal을 claim evidence에서 제외했던 `POC_SPEC.md` §12.5.4를 v2에서 의도적으로 대체한다.

- 같은 요청 안의 상대 시계열 변화
- 같은 normalization group 안의 비교
- 요청 기간·연령·카테고리 metadata가 claim과 일치

서로 다른 요청의 ratio 절대 비교, 절대 검색량·판매량 주장에는 사용할 수 없다.

### 14.2 트렌드 채택

주요 트렌드가 되려면 다음 중 하나를 만족한다.

1. 독립 publisher 2곳 이상
2. Tier A runway 관측 + Tier B 해석 1곳
3. 상품 실측 + 국내 수요 + 편집 근거 중 2축 이상 일치

단일 Tier C만 존재하면 `hypothesis`다.

confidence와 trend stage는 LLM의 자유 선택이 아니다. versioned `trend_rules.yaml`이 evidence axis 수, independent publisher, 관련 field coverage, 시간 FactRef 요구를 정의한다. 기본 판정은 다음과 같다.

- `high`: 주요 트렌드 채택 규칙 충족 + 서로 다른 2축 이상 + 관련 coverage threshold 통과
- `medium`: 채택 규칙은 충족하지만 한 축/coverage가 partial
- `low`: hypothesis 또는 핵심 coverage 부족
- `rising/slowing`: 방향과 기간이 있는 NAVER/newness/editorial timing FactRef 필수
- `mainstream/saturated`: versioned target-brand presence·sale-pressure threshold FactRef 필수
- 위 stage FactRef가 없으면 `hypothesis`

threshold 값과 rule hash는 run manifest에 기록하며 fixture에서 동일 입력→동일 confidence/stage를 검증한다.

### 14.3 Action 근거

모든 `actions[*].evidence_ids`는 다음을 만족한다.

- 최소 1개
- 존재하는 evidence ID
- 액션 rationale과 관련 있음
- 보고서 HTML과 Markdown 모두 노출

### 14.4 저작권

저장·표시 허용:

- URL
- 제목·작성자·게시일
- 구조화 사실
- 짧은 발췌
- image URL과 credit metadata

금지:

- 원문 전체 재배포
- 구독 본문 저장·우회
- runway 이미지 대량 재배포
- 원문을 대체하는 긴 인용

MVP 기본값은 `image_usage=link_only`다. `unknown`도 link-only로 처리하며 remote image를 보고서에 자동 embed·hotlink하지 않는다. `embed_allowed`는 명시적 사용 조건 또는 운영자 승인이 기록되고 credit 요구를 충족한 source에만 설정한다. screenshot fixture는 외부 이미지를 포함하지 않는다.

---

## 15. Hermes 역할과 skill

### 15.1 단일 skill

초기 skill 이름: `md-trend-report`

Hermes skill의 런타임 기본 위치는 활성 profile의 `~/.hermes/skills/`다. 프로젝트와 함께 version control하기 위해 canonical source는 저장소 `hermes/skills/md-trend-report/SKILL.md`에 두고, Phase 1 profile의 `skills.external_dirs`에 저장소 `hermes/skills/`를 등록한다. 운영 profile 외 다른 profile을 자동 수정하지 않는다.

책임:

1. 요청을 `AnalysisRequest`로 구조화
2. Source Registry를 참고해 계획 생성
3. 계획을 Python validator에 전달
4. 사용자 승인 획득
5. Python collector 명령 실행
6. `AnalysisInput` 확인
7. 근거 감사와 보완 수집 여부 결정
8. 리서처·분석가·에디터 역할 실행
9. Python output validator와 renderer 실행
10. 결과 전달

skill은 계산·파싱·렌더링 코드를 포함하지 않는다.

Hermes는 사용자가 `승인`, `시작`, 또는 명시적으로 같은 뜻의 응답을 한 뒤에만 `approval.json`을 생성한다. 파일은 `plan_version`, `plan_hash`, `approved_at`, Hermes session ID를 가진다. Python collector는 plan과 approval의 hash가 같지 않으면 시작하지 않는다. 계획을 수정하면 이전 approval은 무효다.

### 15.2 분석 역할

Researcher:

- evidence를 중복 제거해 사실 단위로 정리
- 출처 간 일치와 상충 표시
- 해석보다 사실 우선

MD Analyst:

- 상품 실측과 수요·에디토리얼 연결
- 브랜드 시그니처
- 가격·컬러·아이템·소재·실루엣 공백
- 기회·위험·액션 작성

Editor:

- 중복 제거
- 과장 제거
- 근거 없는 문장 강등
- MD가 읽는 순서로 정리

Auditor:

- 주요 claim/action evidence 검사
- 실측과 prose 모순 검사
- coverage 은폐 검사
- 단위·통화·segment 검사
- 보완 수집 최대 한 번 제안

역할 간 무제한 대화를 허용하지 않는다. 역할당 기본 1회, 스키마 수정 1회만 허용한다.

### 15.3 모델 호출 위치

Phase 0에서는 기존 Python direct SDK 호출을 허용하는 전환 상태다. Phase 1부터 분석 역할 호출은 Hermes가 소유한다. Python은 JSON input bundle과 validator를 제공한다.

---

## 16. 모순 감사

렌더링 전 코드 검사:

- `products_collected > 0`인데 “상품 데이터 전무” 금지
- price coverage가 존재하는데 “가격 데이터 전무” 금지
- 브랜드 coverage가 일부인데 “시장 전체” 표현 금지
- 통화 혼합 정렬 금지
- requested/observed age mismatch 은폐 금지
- NAVER ratio를 절대량으로 표현 금지
- evidence에 없는 브랜드·가격·수치 인용 금지
- action evidence 누락 금지
- excluded source를 failure denominator에 포함하지 않음

검사 실패 시:

1. 구조화 결과를 한 번 수정 요청한다.
2. 다시 실패하면 해당 claim/action을 제거하거나 limitation으로 강등한다.
3. 감사 경고를 보고서에 표시한다.

---

## 17. Report Quality Contract

배포된 `https://yanghyunu.github.io/md-trend-agent/`는 단순 참고물이 아니라 **canonical golden baseline**이다. 현재 7개 top-level section, 타이포그래피, 카드 밀도, bar·ladder·sparkline, 접이식 appendix와 정보 위계를 그대로 보존한다. v2는 새 renderer로 이를 대체하는 작업이 아니라 기존 renderer와 production 데이터 경로에 coverage, provenance, auditor와 failure truth를 추가하는 작업이다.

구현 전 배포본 HTML, renderer version과 375·768·1280px screenshot을 repository golden fixture로 동결한다. 현재 working tree의 3-product fixture report 또는 이후 생성된 축소 report를 golden으로 사용하지 않는다.

v1→v2 migration은 다음 7개 visual section을 유지하면서 의미 계약을 보강한다.

- 한 장 요약 → Executive Summary + Coverage
- 트렌드 → Runway & Editorial Direction
- 시장 실측 → Market Snapshot + dimension sections
- 브랜드 시그니처 → Brand Signatures / Design Map
- 국내 수요 → Domestic Demand
- 상품 공백 & MD 액션 → Gaps/Opportunities/Risks + MD Actions
- 부록 → Limitations/Failures + Evidence Appendix

### 17.1 필수 visual section

1. 한 장 요약
2. 트렌드 · 권위 근거 T1·T2
3. 시장 실측 스냅샷
4. 브랜드 시그니처
5. 국내 수요 · NAVER 데이터랩
6. 상품 공백 & MD 액션
7. 부록

12개 의미 block은 삭제하지 않고 7개 visual section 안에 배치한다. Coverage/Freshness는 header와 한 장 요약, Design Map과 dimension 분석은 시장 실측·브랜드 시그니처, steady signal은 해당 trend/brand 문맥, limitations/failures/evidence appendix는 부록에 둔다. 의미 block을 이유로 기존 top-level 정보 구조를 해체하지 않는다.

### 17.2 필수 invariant

- 상단에 대상/성공 브랜드 수
- 상품 수와 필드 커버리지
- 수집일·분석 기간·FX 기준일
- 주요 claim에 evidence
- 모든 action에 evidence
- 실패 소스와 원인
- 빈 배열에서도 HTML 생성
- 동적 텍스트 escape
- 위험 URL 제거
- Markdown과 HTML의 의미 일치
- 배포 golden의 상품 분포, 브랜드 signature, trend, NAVER 시계열과 MD action이 동일 production snapshot 재렌더링에서 누락되지 않음
- 본문 evidence는 사람에게 읽히는 source name/title/tier와 원문 link를 우선 표시하고 내부 ID는 보조 metadata로만 표시
- diagnostic fixture renderer와 production renderer composition을 분리
- synthetic `_audited_output()` 또는 3-product fixture가 production analyst와 production data path를 대체하지 않음

### 17.3 빈 데이터 보고서

0개 상품·0개 editorial evidence도 다음을 표시한다.

- 요청 조건
- 승인 계획
- 시도한 source
- 실패 이유
- 수집하지 못한 필드
- 재시도 제안

renderer가 빈 `items_top`, `colors_top`, `materials_top`, `silhouettes_top`을 안전하게 처리해야 한다.

### 17.4 시각 회귀

- 배포된 canonical golden snapshot으로 HTML 생성
- 주요 selector와 section 순서 검사
- pinned Playwright Chromium과 repository font 사용
- viewport 375, 768, 1280px와 desktop 1440×1200, timezone UTC, animation·transition 비활성
- 외부 image/network를 fixture 또는 placeholder로 대체
- 전체 픽셀 중 0.5% 이하 diff를 허용하되 section 누락·overflow·깨진 link는 별도 blocking failure
- empty/partial/full 세 fixture와 production-golden fixture 유지
- 3-product synthetic fixture는 diagnostic 전용이며 production-golden screenshot/hash를 갱신할 권한이 없음

구조·schema·link·security 검사는 CI blocking이다. screenshot diff는 위 환경에서만 blocking으로 사용한다. MD 유용성 평가는 별도 수동 scorecard로 수행하며 자동 테스트와 혼합하지 않는다.

### 17.5 MD 수동 평가

Phase 0C 종료 전 owner가 full report와 partial report를 각각 검토한다.

평가 항목:

- 핵심 판단을 빠르게 찾을 수 있는가
- 근거를 원문까지 추적할 수 있는가
- 상품 실측과 문장이 일치하는가
- MD 액션이 구체적이고 실행 가능한가
- 한계와 실패가 의사결정을 오도하지 않는가
- canonical 배포본보다 정보 탐색성과 MD 활용성이 퇴행하지 않았는가

각 항목은 1~5점과 자유 의견을 기록한다. 증거 추적성과 액션 실행 가능성 중 하나라도 3점 이하이면 Phase 0을 종료하지 않는다. 이 평가는 제품 gate이며 CI test가 아니다.

---

## 18. Run bundle과 저장

### 18.1 Phase 0·1 파일 저장

```text
runs/{run_id}/
  request.json
  plan.json
  approval.json
  source_registry_snapshot.json
  product_records.json
  brand_aggregates.json
  market_rollups.json
  naver_signals.json
  editorial_evidence.json
  runway_observations.json
  steady_signals.json
  evidence_catalog.json
  coverage.json
  collection_failures.json
  analysis_input.json
  researcher.json
  analysis.json
  audit.json
  report.md
  report.html
  manifest.json
```

`manifest.json`은 schema/code/model/provider/prompt/skill/extractor version, 고정 run clock, source registry·normalization dictionary·trend rules·FX·각 산출물 hash를 가진다.

### 18.2 Phase 2 SQLite

최소 테이블:

- `analysis_requests`
- `runs`
- `plan_versions`
- `run_events`
- `sources`
- `source_fetches`
- `products`
- `product_observations`
- `evidence`
- `claims`
- `claim_evidence`
- `reports`

Hermes session transcript를 domain state 원본으로 사용하지 않는다.

---

## 19. 실행 상태

Phase 1 파일 실행:

```text
planned
awaiting_approval
running
rendering
completed
partial_failed
failed
cancelled
```

Phase 2 세부 상태:

```text
draft
planning
awaiting_approval
collecting
auditing
supplementing
researching
analyzing
editing
rendering
completed
partial_failed
failed
cancelled
```

`partial_failed`는 렌더링 완료 후 terminal 상태로만 결정한다.

모든 plan task는 `criticality=required|optional`과 다음 outcome 중 하나를 가진다.

```text
success
no_observation
policy_rejected
auth_failed
source_failed
pagination_incomplete
deadline_exceeded
skipped_optional
```

결정적 판정표:

| 조건 | terminal status |
|---|---|
| 요청 또는 plan schema/policy가 실행 전에 거부됨 | `failed` |
| emergency fallback HTML/Markdown까지 생성 실패 | `failed` |
| 보고서 생성 + blocking audit 0 + 모든 required task `success` 또는 계획상 허용된 `no_observation` | `completed` |
| 보고서 생성 + required task 하나 이상 실패/불완전 또는 required evidence axis 부족 | `partial_failed` |
| optional task만 실패하고 필수 축·audit가 정상 | `completed`, limitation에 optional 실패 노출 |
| 사용자가 중단 | `cancelled` |

`no_observation` 허용 여부는 plan task에 명시한다. NAVER 빈 결과는 허용할 수 있지만 수요 0으로 해석하지 않는다. 상품 required source의 `pagination_incomplete`, eligible 상품 0, 정책 거부는 항상 `partial_failed`다. fallback success는 해당 brand required task를 성공으로 만들 수 있지만 primary 실패는 limitation에 남긴다.

유효 plan 실행이 시작된 뒤 collector, LLM, auditor가 모두 실패해도 Python emergency renderer는 request, 승인 plan, 시도 source, failure code만으로 `report.md/html`을 생성한다. 이 경로까지 실패한 경우에만 “보고서 없음”인 `failed`다.

---

## 20. Discord 경험

Phase 2에서 Hermes native Discord Gateway를 사용한다.

- `DISCORD_AUTO_THREAD=true`로 채널의 새 요청마다 thread를 자동 생성한다.
- thread는 독립 Hermes session namespace를 사용한다.
- 기본 `group_sessions_per_user=true`를 유지해 공유 채널 사용자 기록을 분리한다.
- `DISCORD_ALLOWED_USERS` 또는 `DISCORD_ALLOWED_ROLES`, `DISCORD_ALLOWED_CHANNELS`를 명시한다.
- Message Content Intent를 활성화한다. Server Members Intent는 사용자명·role 기반 허용 정책에 필요하다.
- `@everyone`과 role mention은 비활성 기본값을 유지한다.

### 20.1 계획 메시지

표시:

- 분석 조건
- 대상 11개 브랜드
- 상품 source와 fallback
- NAVER tasks
- editorial 채널
- 예상 URL·브라우저 수
- 예상 deadline
- 제외 소스
- plan version/hash

행동:

- 승인
- 자연어 수정
- 취소

### 20.2 진행 메시지

단계 변경 시에만 갱신한다.

- 현재 단계
- 성공/실패 source
- 수집 상품 수
- evidence 수
- browser fallback 수
- 경고

URL마다 메시지를 보내지 않는다.

### 20.3 결과 메시지

- 핵심 요약
- 커버리지
- 우선 MD 액션
- 실패와 추가 조사 필요
- `report.md`
- `report.html`
- 같은 조건 재실행 방법

### 20.4 권한

run은 `guild_id`, `channel_id`, `thread_id`, `requester_user_id`에 연결한다. 요청자와 운영자만 승인, 수정, 취소, 결과 조회 가능하다.

---

## 21. 수집·분석 예산

### 21.1 수집 예산

초기 기본값:

- 브랜드: 11개
- 브랜드당 primary source: 1개
- 브랜드당 fallback: 최대 1개
- editorial feed: 최대 7개 자동 텍스트 채널
- editorial article fetch: 최대 30개
- 동일 publisher article: 최대 5개
- NAVER 호출: 최대 20회
- DynamicFetcher: 최대 5회
- browser action: 최대 3회
- redirect: 최대 3회
- 응답 본문: 최대 5 MiB
- 일반 HTTP timeout: 20초
- dynamic browser timeout: 60초
- 재시도: 최대 2회
- 429: `Retry-After` 우선, 최대 2회
- 보완 수집: 최대 1회
- LLM schema repair: 역할별 최대 1회
- 전체 기본 deadline: 20분
- 마지막 60초: 신규 수집 금지, fallback 보고서 렌더링

브랜드 상품 pagination도 무제한이 아니다. 승인 plan의 source별 `max_pages`, `max_products`, rate limit, robots crawl delay, 전체 deadline을 모두 지킨다. 빈 page·명시적 last page·중복 page loop 중 하나로 종료 근거를 기록한다. cap 또는 deadline이 먼저 오면 결과를 버리지 않고 `pagination_incomplete`로 표시하며 required 상품 task는 `partial_failed`가 된다. “전량·전 variant”는 고정 fixture의 알려진 page/variant count에 대해 blocking CI로 검증하고, 변동하는 live catalog에서는 completeness 상태를 정직하게 보고한다.

### 21.2 LLM context 예산

- raw ProductRecord 전체는 역할 prompt에 넣지 않는다.
- 역할별 기본 입력 상한은 model tokenizer 기준 48,000 tokens, 출력 상한은 8,000 tokens다. 실제 provider 한도가 더 작으면 더 작은 값을 사용한다.
- Researcher는 질문별 aggregate와 dedupe된 evidence summary를 받고 publisher/question 단위로 chunk한다.
- Analyst는 merged research, CoverageMetrics, BrandAggregate, MarketRollup, EvidenceRef catalog만 받는다.
- Auditor는 AnalysisOutput과 참조된 evidence/FactRef만 받고 미참조 raw record는 조회하지 않는다.
- Editor는 audit 통과 output과 report metadata만 받으며 새 claim을 만들 수 없다.
- 입력 상한을 넘으면 alias·중복, Tier C, 오래된 optional evidence 순으로 결정적으로 축약한다. required coverage/failure, claim이 참조한 evidence, aggregate provenance는 제거하지 않는다.
- chunk merge도 같은 `Claim` schema를 사용하며 중복 claim은 evidence union 후 deterministic key로 병합한다.
- token estimate, 실제 input/output tokens, model/provider, 축약 규칙 version을 manifest에 기록한다.
- provider timeout/overflow 후 한 번의 축약 재시도만 허용하고 실패하면 deterministic fallback report로 강등한다.

---

## 22. 안전·정책

- 공개 `http/https`만 수집
- robots.txt와 이용약관 준수
- 식별 가능한 전용 User-Agent 사용
- 로그인·유료·CAPTCHA·SNS 자동 수집 금지
- 차단 우회·proxy rotation 금지
- URL credentials 금지
- 80/443만 허용
- DNS와 redirect hop마다 public IP 검증
- private, loopback, link-local, metadata endpoint 차단
- redirect·byte·MIME 제한
- run별 domain allowlist
- Phase 0·1의 `user_source_urls`는 기존 active Registry host/path와 일치할 때만 자동 사용; 신규 host는 manual review 전 fetch 금지
- 웹 콘텐츠를 비신뢰 data-only 입력으로 전달
- 웹 텍스트가 tool argument나 정책을 만들지 못함
- HTML escape·sanitizer·CSP
- `javascript:`·event handler·위험 SVG 제거
- Discord mention escape
- 비밀은 environment 또는 secret store
- 로그·보고서에서 secret 제거
- 원문과 원본 이미지 재배포 금지

Fashionista robots의 `/api/` 금지를 존중해 RSS와 공개 HTML만 사용한다. Highsnobiety generic crawler는 최소 1초 crawl delay를 적용한다. Vogue의 구독·AI crawler 제한을 우회하지 않는다.

---

## 23. 오류 처리

- primary source 실패: exact-match fallback 1개 시도
- fallback 실패: 브랜드 failure 기록, 전체 계속
- HTTP 200 + 상품 0: `empty_source`
- 브랜드 오탐: `brand_mismatch`
- pagination 불명: `pagination_incomplete`
- NAVER 인증 실패: 정량 축 부분 실패
- NAVER 빈 결과: `no_observation`, 수요 0으로 해석 금지
- RSS 실패: sitemap 또는 공개 index 사용
- article partial/paywall: metadata와 공개 발췌만 저장
- DynamicFetcher 실패: 우회하지 않고 실패 기록
- FX 실패: 직전 유효 캐시, 없으면 통화별 분리
- LLM schema 실패: repair 1회 후 단계 강등
- evidence 누락: claim/action 제거 또는 hypothesis
- normal renderer 실패: dependency-free emergency renderer 1회
- emergency renderer도 실패: `failed`

모든 오류는 기계 판독 가능한 `failure_code`, source, 시각, retry count, 짧은 메시지를 가진다.

---

## 24. 테스트 전략

### 24.1 단위 테스트

- Source Registry 우선순위
- exact brand 검증
- Shopify pagination
- variant min/max·sale·availability
- product/variant identity·eligibility·canonical URL·content hash invariants
- JSON-LD·hydration parsing
- RSS parsing
- editorial sponsored/affiliate 분류
- currency normalization
- color family mapping
- evidence ID validation
- contradiction rules
- empty renderer
- HTML escape·URL validation
- DNS rebinding·IPv4/IPv6 private/loopback/link-local/metadata 차단
- redirect 각 hop의 scheme·port·IP 재검증
- MIME allowlist·5 MiB 초과 중단
- registry host/path allowlist와 신규 user URL 거부
- read-only XHR 허용, mutation/session cookie/signed token 거부
- robots/terms policy 만료·hash 변경 시 manual review 강등

### 24.2 adapter fixture 테스트

고정 HTML/JSON fixture:

- Shopify
- Breuninger JSON-LD
- SSF product cards
- Quince `__NEXT_DATA__`
- SSG product cards
- Kolon Next.js/public product endpoint result
- Vogue partial collection
- Fashionista full article
- Highsnobiety full article
- RSS feeds

live 페이지를 결정적 CI 조건으로 사용하지 않는다.

### 24.3 통합 테스트

- request에서 report까지 full fixture pipeline
- AnalysisInput 각 field가 실제 role payload 또는 manifest locator에 포함되는지 검증
- 동일 run/plan evidence만 claim이 참조하고 alias가 독립 근거로 중복 계산되지 않는지 검증
- aggregate를 원 ProductRecord manifest에서 재계산해 AGG evidence와 일치하는지 검증
- primary 실패 후 fallback
- Scrapling 자동수집 실패 후 ManualObservationTask 생성과 validated evidence 편입
- 자동·수동·blocked·missing coverage 분리
- 일부 브랜드 실패
- 모든 브랜드 실패
- NAVER 실패
- editorial 실패
- mixed currency
- analysis contradiction rejection
- stale evidence ID rejection
- Markdown/HTML action evidence 일치
- collector·LLM·auditor 실패 후 emergency report 생성
- required/optional task outcome matrix의 completed/partial_failed/failed 판정
- network-disabled full fixture pipeline은 기준 CI runner에서 180초 timeout 안에 종료; live source 성능 SLA로 해석하지 않음

### 24.4 Report Quality Contract

fixture:

1. `production_golden` — 현재 배포 snapshot
2. `full_success`
3. `partial_failure`
4. `empty_failure`
5. `diagnostic_three_product` — production 완료 판정 제외

검사:

- 필수 section
- coverage 상단 표시
- evidence link
- action evidence
- limitation
- 안전한 HTML
- screenshot regression
- 7-section golden structure와 human-readable evidence label
- production composition 경로가 fixture-only synthetic analyst를 사용하지 않는지 검증

### 24.5 live smoke test

수동 opt-in:

- 대상 source 1회 최소 요청
- robots 확인
- 접근 상태
- 상품 record 1개 이상
- feed item 수
- schema drift

POC live smoke는 public source의 자동수집 가능성을 검증하는 opt-in 실행이다. production contract 부재만으로 금지하지 않는다. 작은 request/page/product cap과 deadline을 적용하고 raw body를 장기 artifact로 보존하지 않는다.

live smoke 결과는 CI pass/fail과 분리한다.

---

## 25. 수용 기준

### Phase 0A — 코어 연결

- Le Cashmere가 실행 target에서 제거되고 PLUSH’MERE가 target registry에 포함된다.
- Shopify 6개 fixture의 모든 page와 variant가 보존되고 variant invariant를 통과한다.
- `AnalysisInput`의 상품 집계, coverage, failures, NAVER, steady가 실제 role payload 또는 hash-검증 가능한 manifest locator에 연결된다.
- 모든 major Claim/Action이 같은 run/plan의 유효 evidence와 FactRef를 가진다.
- 집계 evidence를 원 ProductRecord에서 재계산할 수 있다.
- 빈 데이터와 collector/LLM/auditor 실패에서도 emergency report.md/html이 생성된다.
- 혼합 통화는 통화별 분리 또는 동일 FX 기준 KRW로 표시된다.
- Phase 0A full/partial/empty fixture와 security blocking tests가 통과한다.
- 기존 production 수집·NAVER·분석·renderer 경로가 유지되며 3-product synthetic fixture output으로 대체되지 않는다.
- canonical 배포 report의 7-section 구조와 핵심 component가 production snapshot 재렌더링에서 보존된다.

### Phase 0B — 상품 source 확장

- 11개 target과 Le Cashmere 제외가 Source Registry에 존재한다.
- Scrapling이 POC 기본 scraper로 배선되고 공개·비로그인 source의 bounded 자동수집이 production composition 경로에서 실행된다.
- 비-Shopify 5개 각각에 policy review·fixture hash·exact-brand·eligibility·pagination 검증을 통과한 primary 또는 fallback adapter가 있다.
- adapter 실패 또는 `manual_only` source가 수동 관찰 task와 validated evidence로 이어진다.
- live cap/deadline 전 pagination 종료를 증명하지 못하면 `pagination_incomplete`와 `partial_failed`가 된다.
- live smoke drift는 CI와 분리되며 registry 시각·상태·failure code로 남는다.

### Phase 0C — 패션 evidence와 v2 report

- NAVER, editorial, runway, steady contract가 `AnalysisInput`과 evidence catalog에 연결된다.
- Tavily 런타임 경로가 제거되고 허용된 RSS/sitemap/static source만 자동 사용한다.
- independent publisher와 access-status eligibility가 결정적으로 판정된다.
- canonical 7-section production golden과 full/partial/empty report의 action evidence·시각 회귀가 통과한다.
- 분석이 FactRef 또는 source data와 모순되면 renderer 전에 차단·강등된다.

### Phase 1

- Hermes가 자연어 요청을 `AnalysisRequest`로 구조화한다.
- 사용자 승인 전 수집하지 않는다.
- 승인 plan version/hash만 실행한다.
- Hermes가 Python domain commands를 호출한다.
- run bundle 전체가 생성된다.
- Hermes가 HTML/Markdown 파일을 전달한다.

### Phase 2

- Discord thread에서 계획 수정·승인·취소 가능하다.
- SQLite가 domain state 원본이다.
- Hermes 재시작 후 마지막 안전 단계에서 복구 가능하다.
- stale·중복 승인을 거부한다.
- 권한 없는 사용자가 run을 조작할 수 없다.

### Report 품질

- MD가 핵심 요약, 시장 실측, 국내 수요, 런웨이·에디토리얼, 브랜드 시그니처, MD 액션, 한계를 한 리포트에서 확인한다.
- 주요 claim과 action의 근거를 클릭해 원문으로 이동할 수 있다.
- 커버리지와 실패가 숨겨지지 않는다.
- unsupported recommendation이 없다.

---

## 26. 구현 순서

1. `ProductRecord` variant·eligibility와 공통 Evidence/FactRef Pydantic 계약
2. 현재 pipeline에서 datalayer·steady·coverage·failure를 실제 `AnalysisInput`/model payload에 연결
3. aggregate provenance와 contradiction auditor
4. 빈 데이터·LLM 실패 emergency renderer와 action evidence
5. 통화·variant·Le Cashmere/PLUSH’MERE target 수정
6. Phase 0A fixture·security·report tests
7. Source Registry와 policy validator seed
8. Scrapling static adapters
9. 제한된 DynamicFetcher/XHR adapters
10. Phase 0B adapter fixture·live smoke 분리
11. NAVER contract/client tests
12. editorial RSS·sitemap·article collector와 Tavily 제거
13. runway observation collector
14. trend adoption·publisher independence
15. v2 Report Quality Contract tests와 Phase 0C golden
16. root `AGENTS.md`
17. `md-trend-report` Hermes skill
18. Python atomic CLI
19. Hermes Desktop 승인 흐름
20. Hermes MVP release gate(0A·0B·0C·1)
21. Discord Gateway
22. SQLite durability/recovery
23. Operational MVP release gate
24. 필요 시 FastAPI·worker·Docker

1~6은 선행 core gate다. 이후 7~15(source/report lane)와 16~19(Hermes lane)는 병렬 진행할 수 있다. Hermes MVP release는 두 lane과 해당 fixture 수용 기준이 모두 통과한 뒤에만 선언한다.

---

## 27. 제외 범위

현재 MVP 완료 조건이 아니다.

- 자동 발주
- 판매 예측
- 재고 최적화
- Graph DB
- 이미지 AI 판독
- FashionCLIP
- Instagram 자동 수집
- 로그인·유료 콘텐츠
- PDF·PowerPoint
- 조직 단위 복잡한 RBAC
- 대규모 범용 crawler
- 다중 지역 분산 worker
- 자동 변경 감지와 상시 모니터링

cron은 수동 run 품질과 Discord 흐름이 안정된 뒤 별도 추가한다.

---

## 28. 알려진 위험

- retailer 검색 결과가 exact brand가 아닐 수 있음
- 국가·쿠키·재고에 따라 상품 수·가격이 달라짐
- 사이트 구조와 RSS가 변경될 수 있음
- editorial 기사 빈도가 실제 수요와 다름
- Vogue 등 접근 정책이 변경될 수 있음
- image 사용권이 source별로 다름
- LLM이 evidence를 잘못 연결할 수 있음
- adaptive selector가 조용히 잘못된 element를 선택할 수 있음
- 환율 fallback이 최신 시장 환율과 다를 수 있음

완화:

- exact brand 검증
- source snapshot과 collected_at
- fixture와 live smoke 분리
- evidence validation
- coverage·failure 노출
- 명시적 selector 우선
- 원문 링크와 짧은 발췌

---

## 29. 최종 제품 정의

```text
사용자 요청
→ Hermes 조사 계획
→ 사용자 승인
→ 정책에 맞는 상품·수요·패션 근거 수집
→ Python 정규화·집계
→ Hermes 분석·근거 감사
→ Python 모순 검증·결정적 렌더링
→ MD 의사결정 리포트
```

최종 제품의 핵심은 crawler 수, agent 수, 화려한 HTML이 아니다.

> 불완전한 패션 데이터를 실패와 한계까지 포함해 반복 가능하고 감사 가능한 MD 결정으로 변환하는 것.

---

## 30. 참고 문서

- 기존 목표 명세: `SPEC.md`
- PoC 명세와 실측 결정: `POC_SPEC.md`
- 기준 HTML: `out/report.html`
- 브랜드 유통처 조사: `.hermes/desktop-attachments/Brand.md`
- Scrapling: https://github.com/d4vinci/Scrapling
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs
- Hermes Agent repository: https://github.com/NousResearch/hermes-agent
- NAVER API HUB: https://api.ncloud-docs.com/docs/naver-api-hub-overview
- Crawl4AI: https://github.com/unclecode/crawl4ai
