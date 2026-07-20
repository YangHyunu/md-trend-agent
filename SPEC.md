# 캐시미어·니트웨어 MD 트렌드 에이전트 MVP 설계

## 1. 문서 상태

- 기준일: 2026-07-19
- 단계: MVP
- 사용자 인터페이스: Discord
- 에이전트 런타임: Hermes Agent
- 워크플로우 엔진: Hermes Agent 단독 사용
- 저장소: SQLite

이 문서는 구현 기준이 되는 MVP 명세다. Graph DB, 자동 예약 실행, 이미지 자체 분석은 향후 확장으로 남긴다.

## 2. 목적

여성 캐시미어·니트웨어 브랜드 MD가 Discord에서 관심 브랜드, 사이트, 카테고리, 타깃, 가격대, 시장, 기간, 키워드를 입력하면 Hermes Agent가 조사 계획을 제안하고 승인받은 범위에서 국내 수요 데이터와 공개 웹 자료를 수집한다.

시스템은 수집한 근거를 바탕으로 경쟁 브랜드 아이템, 주요 트렌드, 컬러, 소재, 실루엣, 디테일, 가격 구성을 분석하고 MD가 실행할 수 있는 상품 기획 제안을 Markdown과 HTML 보고서로 제공한다.

MVP는 완벽한 트렌드 예측보다 다음 가치에 집중한다.

- 반복 가능한 조사 과정
- 조사 계획에 대한 사용자 통제
- 모든 주요 주장과 출처의 연결
- 실패와 근거 부족의 투명한 표시
- 실제 상품 기획으로 이어지는 MD 액션

## 3. 핵심 사용자 흐름

1. 사용자가 Discord에서 분석 조건, 브랜드, URL을 입력한다.
2. Hermes가 조사 질문, 검색어 묶음, 출처 유형, 수집 예산을 포함한 수집 계획을 만든다.
3. 정책 검증기가 계획의 형식, 안전, 비용, API 제한을 검사한다.
4. Hermes가 검증된 계획을 Discord에 보여준다.
5. 사용자가 계획을 승인하거나 자연어로 수정한다.
6. 시스템이 NAVER API HUB, 웹 검색, 등록 URL에서 자료를 수집한다.
7. 근거 감사자가 주요 조사 질문에 필요한 근거가 있는지 평가한다.
8. 근거가 부족하면 정책 한도 안에서 보완 수집을 최대 한 번 수행한다.
9. 리서처, MD 분석가, 에디터가 순차 실행된다.
10. Discord에 진행 상황, 핵심 요약, 실패 출처, Markdown 및 HTML 보고서를 제공한다.

## 4. MVP 범위

### 포함

- Discord 기반 입력, 승인, 상태 확인, 결과 전달
- 브랜드 세트와 참고 URL 저장
- 자연어 입력을 구조화된 분석 조건으로 변환
- Hermes 기반 수집 계획 생성
- 코드 기반 정책 검증
- 선택적 로컬 LLM 기반 의미 검증
- NAVER API HUB Search Trend 및 Shopping Insight
- 웹 검색을 통한 신규 URL 발견
- Crawl4AI 기반 공개 페이지 추출
- Browser Use 기반 제한적 fallback
- 근거 충분성 감사와 최대 한 번의 보완 수집
- 리서처, MD 분석가, 에디터 역할의 순차 실행
- SQLite에 요청, 계획, 실행, 출처, 근거, 주장, 보고서 저장
- Markdown 및 HTML 보고서
- 출처 연결 썸네일과 페이지 텍스트 기반 설명
- 동일 조건 수동 재실행

### 제외

- 자동 예약 실행과 지속 모니터링
- 이전 실행과 현재 실행의 자동 변경 감지
- 로그인 사이트와 유료 콘텐츠
- Instagram 등 SNS 자동 크롤링
- CAPTCHA 우회, 프록시 회전, 차단 회피
- 이미지 자체의 컬러·소재·실루엣 AI 판독
- FashionCLIP 및 멀티모달 이미지 분석
- Graph DB
- PDF 및 PowerPoint 생성
- 자동 발주, 판매 예측, 재고 최적화
- 범용 대규모 크롤링 인프라
- 다중 사용자 조직 권한 관리

## 5. 기술 선택

### Hermes Agent

Hermes Agent가 유일한 에이전트 오케스트레이터다. Discord Gateway, skill, tool 호출, subagent, 모델 선택 기능을 사용한다. LangGraph와 OpenClaw는 MVP에 사용하지 않는다.

Hermes 고유 형식은 `Orchestrator` 인터페이스 뒤에 격리한다. FastAPI와 도메인 모델은 Hermes의 세션, 메시지, skill 내부 타입에 직접 의존하지 않는다.

### FastAPI

FastAPI는 Discord/Hermes가 호출하는 내부 애플리케이션 API를 제공한다. 입력 검증, 실행 생성, 승인, 상태 조회, 저장소 접근, 도구 호출 경계를 담당한다. 에이전트의 자유 대화를 직접 구현하지 않는다.

### LLM

강한 외부 모델 하나를 수집 계획가, 리서처, MD 분석가, 에디터 역할에 재사용할 수 있다. 각 역할은 별도 skill, 시스템 지시, Pydantic 입출력 스키마를 가진다.

로컬 LLM은 선택적으로 수집 계획의 관련성, 중복, 출처 편향, 누락을 검토한다. 로컬 LLM 결과는 코드 정책을 우회할 수 없다.

### NAVER API HUB

신규 MVP는 기존 `openapi.naver.com` DataLab API를 사용하지 않는다. NAVER Cloud Platform의 NAVER API HUB만 사용한다.

- Base URL: `https://naverapihub.apigw.ntruss.com`
- 인증: `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`
- Search Trend: `POST /search-trend/v1/search`
- Shopping Insight 분야별: `POST /shopping/v1/categories`
- Shopping Insight 키워드별: `POST /shopping/v1/category/keywords`
- Search Trend: 월 최대 50,000건
- Shopping Insight: 월 최대 50,000건
- API Key당 최대 50 RPS

Search Trend와 Shopping Insight의 `ratio`는 절대 검색량이나 클릭량이 아니다. 각 요청 결과의 최대값을 100으로 둔 상대값이며 서로 다른 요청의 값을 절대량처럼 직접 비교하지 않는다.

MVP에서 사용하는 요청 제약은 다음과 같다.

- Search Trend: 2016-01-01부터, `date|week|month`, 최대 5개 그룹, 그룹당 최대 20개 검색어
- Shopping Insight: 2017-08-01부터, `date|week|month`
- Shopping 분야별: 최대 3개 카테고리 그룹
- Shopping 키워드별: 최대 5개 키워드 그룹, 그룹당 검색어 1개
- Shopping 카테고리 코드는 네이버쇼핑 `cat_id`를 검증해 사용

### Web Discovery

검색 공급자는 교체 가능한 `SearchProvider` 인터페이스로 둔다. MVP 기본 구현은 Tavily다. 검색 결과 요약문은 최종 근거로 사용하지 않고 원문 URL을 다시 수집한다.

### Crawl4AI

공개 페이지를 Markdown 또는 구조화 데이터로 추출하는 기본 수집기다. 비동기 API를 사용하고 보안 패치가 포함된 버전을 고정한다.

### Browser Use

Crawl4AI가 충분한 내용을 얻지 못하고 클릭, 스크롤, JavaScript 렌더링이 필요할 때만 실행한다. 실행별 허용 도메인을 적용하고 로그인, CAPTCHA, 차단 회피를 수행하지 않는다.

### SQLite

단일 인스턴스 MVP 저장소다. 애플리케이션 데이터는 저장소 인터페이스 뒤에 격리한다. 엔터티 ID와 관계 테이블을 명시적으로 관리해 향후 Graph DB로 이관하거나 이중 기록할 수 있게 한다.

### Docker Compose

`api`, `hermes`, `collector`, `browser-worker`를 분리한다. Hermes 전체 프로세스와 브라우저 수집기를 격리하고 최소한의 볼륨과 네트워크만 허용한다.

## 6. 시스템 경계

### Discord Gateway

- Hermes가 Discord 메시지를 수신한다.
- 분석마다 Discord thread 하나를 사용한다.
- 자유 텍스트를 분석 요청 초안으로 변환한다.
- 계획 승인, 수정, 취소, 상태 조회, 보고서 전달을 처리한다.
- 설정된 Discord 서버, 채널, 사용자 allowlist만 허용한다.

### Request API

- 구조화된 분석 조건을 검증한다.
- 요청과 실행 레코드를 만든다.
- Hermes가 사용할 내부 tool API를 제공한다.
- 수집 또는 LLM 분석 로직을 직접 수행하지 않는다.

### Orchestrator Adapter

```python
class Orchestrator:
    async def create_plan(self, request_id: str) -> "CollectionPlan": ...
    async def revise_plan(self, run_id: str, instruction: str) -> "CollectionPlan": ...
    async def start(self, run_id: str, plan_version: int) -> None: ...
    async def resume(self, run_id: str) -> None: ...
    async def cancel(self, run_id: str) -> None: ...
```

MVP 구현체는 `HermesOrchestratorAdapter`다. 향후 런타임 교체 시 FastAPI, 저장소, 수집기, 보고서 렌더러를 변경하지 않는다.

Hermes만 단계 순서와 다음 작업을 결정한다. FastAPI는 원자적인 command/query, 상태 전이 검증, 정책 집행, 저장만 담당하며 workflow scheduling, 재시도 분기, 다음 단계 선택을 수행하지 않는다.

- Hermes는 실행 시작 시 60초 run lease를 얻는다.
- 실행 중 20초마다 heartbeat를 갱신한다.
- lease가 만료되면 다른 Hermes worker가 마지막 완료 단계에서 재개할 수 있다.
- 단계별 `run_id + step_name + attempt`를 멱등성 키로 사용한다.
- Discord 승인 이벤트가 현재 `plan_version`과 함께 Hermes를 깨운다.
- 취소 이벤트는 상태를 `cancelled`로 바꾸고 진행 중 외부 호출 종료 후 다음 단계 진입을 막는다.

### Collection Planner Skill

사용자 조건을 다음 구조로 변환한다.

- 조사 질문
- 비교 브랜드와 경쟁군
- 검색어 및 쇼핑 키워드 묶음
- 필요한 출처 유형
- NAVER API HUB 요청 조합
- 직접 등록 URL
- 검색 질의 수
- 수집 URL 상한
- Browser Use 상한
- 중단 조건

### Collection Policy Validator

#### 코드 검증

- Pydantic 스키마
- 날짜, 연령, 시장, 가격대
- 공개 `http/https` URL
- 내부 IP, localhost, metadata endpoint 차단
- 도메인 허용·차단 정책
- 검색 질의와 URL 개수 상한
- Browser Use 횟수 상한
- NAVER API HUB 50 RPS 이하 제한
- 보완 수집 최대 한 번
- 로그인, CAPTCHA, SNS 자동 수집 금지
- API별 날짜, time unit, 그룹, 키워드, 카테고리 수 제한

코드 정책 위반은 무조건 차단한다.

#### 로컬 LLM 의미 검증

- 조사 질문과 검색어의 관련성
- 브랜드, 가격, 카테고리 누락
- 검색어 중복
- 공식 사이트 편향
- 출처 유형 다양성
- 계획이 조사 질문에 답할 가능성

로컬 LLM은 `approve`, `revise`, `uncertain` 중 하나를 구조화해 반환한다. `uncertain`은 Discord 사용자 확인으로 전환한다.

로컬 LLM이 구성되지 않았거나 호출에 실패하면 코드 검증 결과와 사용자 승인을 사용한다. 로컬 LLM 장애가 전체 실행을 막지 않는다.

### Source Registry

브랜드와 URL을 관리한다.

- 브랜드명
- 정규화된 이름
- 공식 URL
- 채널 유형
- 추적 목적 태그
- 사용자 메모
- 활성 상태
- 마지막 수집 상태와 시각

MVP의 추적은 자동 감시가 아니라 저장된 조건과 소스를 수동 재실행하는 의미다.

### DataLab Client

- NAVER API HUB 인증
- Search Trend 요청
- Shopping Insight 요청
- 요청 정규화
- 월별 호출량 추적
- client-side rate limit
- 429 backoff
- 부분 실패 기록

검색 트렌드의 25~39세 코드는 `4`, `5`, `6`이다. 쇼핑인사이트의 20~39세 코드는 `20`, `30`이다. 두 API의 연령 코드 체계를 혼용하지 않는다.

Shopping Insight는 25~39세를 정확히 표현할 수 없고 20~39세만 제공한다. 정규화 결과에 다음을 저장하고 보고서에 의무 표시한다.

```json
{
  "requested_segment": "25-39",
  "observed_segment": "20-39",
  "coverage_mismatch": true
}
```

Shopping Insight 결과를 정확한 25~39세 신호로 표현하지 않는다.

### Web Discovery

- 분석 조건과 수집 계획을 검색 질의로 변환한다.
- 후보 URL과 발견 경로를 반환한다.
- 동일 canonical URL을 중복 제거한다.
- 동일 도메인 편중을 제한한다.

### Content Collector

1. Crawl4AI로 수집한다.
2. 본문이 500자 미만이고 구조화된 상품·콘텐츠 항목도 3개 미만이면 추출 실패로 판정한다.
3. Browser Use로 한 번 재시도한다.
4. 다시 실패하면 URL과 오류 유형을 저장한다.

임계값은 설정으로 관리한다.

### Evidence Store

모든 근거를 공통 형식으로 저장한다.

- 안정적인 UUID
- 출처 URL과 canonical URL
- 제목
- 게시일 또는 `게시일 확인 불가`
- 수집일
- 원문 발췌
- 수치와 단위
- 브랜드
- 카테고리
- 상품명
- 가격과 통화
- 소재·컬러·실루엣·디테일 텍스트
- 이미지 URL
- 수집 방법
- 콘텐츠 해시
- 신뢰도 입력값

원문 전체와 원본 이미지를 재배포하지 않는다. 분석에 필요한 최소 발췌, 출처 링크, 출처 연결 썸네일만 사용한다.

### Evidence Auditor Skill

조사 질문별로 다음을 평가한다.

- 정량 신호 존재 여부
- 공식 출처 존재 여부
- 독립 웹 출처 수
- 상충 자료 여부
- 가격, 소재, 컬러, 실루엣 등 필수 필드 누락

근거가 부족하면 부족 항목만 포함한 보완 계획을 만든다. 정책 검증 후 최대 한 번 실행한다. 한도 도달 후에도 부족하면 보고서에 `추가 조사 필요`로 표시한다.

### 기본 수집 예산

- 검색 질의: 누적 최대 12개
- 발견 URL: 누적 최대 60개
- 실제 수집 URL: 누적 최대 30개
- 동일 도메인 수집 URL: 누적 최대 5개
- NAVER 호출: 누적 최대 20회
- Browser Use fallback: 누적 최대 5회
- redirect: 요청당 최대 3회
- 응답 본문: 페이지당 최대 5 MiB
- Tavily·NAVER timeout: 호출당 20초
- Crawl4AI timeout: URL당 60초
- Browser Use timeout: URL당 120초
- 네트워크 재시도: 호출당 최대 2회
- 429 재시도: 최대 2회, `Retry-After` 우선, 대기당 최대 10초
- 보완 수집: 최대 1회
- LLM 스키마 수정 요청: 단계별 최대 1회
- 전체 wall-clock deadline: 15분
- 최종 경고 보고서 렌더링 예약 시간: 마지막 60초

최초 계획과 보완 계획은 같은 누적 예산을 공유한다. FastAPI가 예산을 원자적으로 차감하며 Hermes는 남은 예산보다 큰 작업을 만들 수 없다. 사용자가 더 작은 한도를 요청할 수 있지만 더 큰 한도는 MVP에서 허용하지 않는다. 실행 14분이 지나면 새 수집·분석 작업을 시작하지 않고 현재 결과와 실패 기록으로 렌더링 단계에 진입한다. 전체 15분 안에 경고 보고서를 만든 뒤 `partial_failed`로 종료한다.

### Analysis Skills

#### 리서처

근거를 중복 제거하고 사실, 수치, 발췌, URL, 수집일을 묶는다. 해석보다 사실 정리에 집중한다.

#### MD 분석가

다음을 구조화해 작성한다.

- 상승, 주류, 포화, 둔화 트렌드
- 경쟁 브랜드 아이템
- 컬러, 소재, 실루엣, 디테일
- 타깃과 가격 적합성
- 상품 구성 공백
- 기회와 위험
- 실행 가능한 MD 액션

#### 에디터

중복, 모순, 근거 없는 주장을 제거한다. 모든 주요 주장과 추천 액션에 근거 ID를 연결한다. 근거가 약하면 가설 또는 추가 조사 필요로 낮춘다.

각 분석 skill은 한 번 실행한다. Pydantic 스키마 검증에 실패할 때만 원문 결과를 보존하고 수정 요청을 한 번 허용한다. skill끼리 무제한 대화하지 않는다.

### Report Renderer

구조화된 결과를 Markdown과 HTML로 렌더링한다. LLM이 최종 HTML을 자유 생성하지 않는다.

## 7. Hermes MVP 워크플로우

```text
Discord 입력
→ 요청 구조화
→ 수집 계획
→ 코드 정책 검증
→ 선택적 로컬 LLM 의미 검증
→ Discord 계획 승인
→ NAVER·웹 수집
→ 근거 감사
→ 필요 시 보완 수집 1회
→ 리서처
→ MD 분석가
→ 에디터
→ Markdown·HTML 렌더링
→ Discord 전달
```

### 실행 상태

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

모든 상태 변경은 SQLite에 기록한다. Hermes 세션 기록만 실행 상태의 원본으로 사용하지 않는다.

부분 실패는 중간 terminal 상태가 아니다. 실행 중에는 다음 outcome 필드로 누적한다.

```text
has_partial_failures: bool
warnings: list[Warning]
failure_reasons: list[FailureReason]
```

최종 상태 `partial_failed`는 렌더링이 끝난 뒤에만 결정한다.

허용 상태 전이는 다음으로 제한한다.

```text
draft → planning → awaiting_approval
awaiting_approval → planning | collecting | cancelled
collecting → auditing | rendering | failed | cancelled
auditing → supplementing | researching | rendering | failed | cancelled
supplementing → auditing | rendering | failed | cancelled
researching → analyzing | rendering | failed | cancelled
analyzing → editing | rendering | failed | cancelled
editing → rendering | failed | cancelled
rendering → completed | partial_failed | failed
```

허용되지 않은 전이는 `409 Conflict`로 거부한다.

최소 한 개의 근거가 있으면 가능한 분석 단계를 계속 실행한다. 근거가 하나도 없어도 요청, 승인된 계획, source fetch 실패 기록으로 결정적인 `근거 수집 실패 보고서`를 렌더링한 뒤 `partial_failed`로 종료한다. 요청·계획 자체가 유효하지 않거나 renderer가 실패해 보고서를 만들 수 없을 때만 `failed`로 종료한다.

장시간 실행은 요청 응답과 분리한다. FastAPI는 실행 생성 후 `202 Accepted`와 `run_id`를 반환하고 Hermes가 백그라운드에서 진행한다. 각 단계는 시작 전후 상태와 멱등성 키를 기록한다.

## 8. Discord 경험

### 입력 예

```text
@MD-Agent cashmere-reference 브랜드 세트로 분석해줘.

카테고리: 여성 니트웨어
타깃: 한국 여성 25~39세
가격대: 20만~70만원
기간: 최근 8주
중점: 경쟁 아이템, 컬러 조합, 주요 소재, 독특한 캐시미어 아이템
```

### 계획 확인

Hermes는 다음을 표시한다.

- 사용할 브랜드와 URL
- DataLab 키워드 묶음
- 검색할 출처 유형
- 예상 검색 질의 수
- 최대 수집 URL 수
- Browser Use 상한
- 예상 분석 단계

사용자는 `시작`, `취소`, 자연어 수정 중 하나를 선택한다.

모든 계획은 증가하는 `plan_version`과 내용 `plan_hash`를 가진다. 수정하면 `awaiting_approval → planning → awaiting_approval`로 이동하고 새 버전을 만든다. 승인 요청은 승인 대상 버전과 멱등성 키를 포함한다. 구버전·중복 승인은 `409 Conflict`로 거부한다. 24시간 동안 승인하지 않으면 실행을 `cancelled`로 종료한다. 수집 시작 후 계획 수정은 허용하지 않으며 수정된 조건으로 새 run을 생성한다.

### 진행 상태

Discord thread에 단계 변경 시점만 업데이트한다.

- 현재 단계
- 수집 성공·실패 수
- 근거 수
- Browser Use 전환 수
- 부분 실패 이유

개별 URL마다 메시지를 보내지 않는다.

### 결과 전달

- Discord 핵심 요약
- 신뢰도 높은 주장 수
- 추가 조사 필요 항목
- 실패 출처 수
- Markdown 파일
- HTML 파일 또는 내부 보고서 URL
- 같은 조건 재실행 명령

run은 `guild_id`, `channel_id`, `thread_id`, `requester_user_id`에 바인딩한다. 요청자와 설정된 운영자만 계획 수정, 승인, 취소, 보고서 조회를 수행할 수 있다. 보고서 URL은 인증된 내부 endpoint 또는 24시간 만료 signed URL로 제공한다.

## 9. 보고서 구조

1. 한눈에 보는 핵심 요약
2. Design Map
3. 상승, 주류, 포화, 둔화 트렌드
4. 경쟁 브랜드별 주요 아이템
5. 컬러 조합
6. 소재, 실루엣, 디테일 변화
7. 타깃 연령 및 가격대 적합성
8. 상품 구성 공백
9. 상품화 기회와 위험
10. MD 추천 액션
11. 데이터 한계와 수집 실패
12. 출처, 수집일, 신뢰도

### Design Map 정의

MVP의 Design Map은 이미지 임베딩 공간이나 자동 군집 지도가 아니다. 브랜드를 행으로 두고 다음 항목을 열로 비교하는 근거 기반 매트릭스다.

- 핵심 아이템
- 컬러 조합
- 소재 표현
- 실루엣
- 차별화 디테일
- 가격대
- 참고 이미지 링크
- MD 시사점

모든 셀은 근거 ID를 참조한다. 자료가 없으면 추정하지 않고 `근거 없음`으로 표시한다.

### 이미지 취합

MVP는 다음만 제공한다.

- 출처 페이지의 이미지 URL
- 출처 연결 썸네일
- 상품명, 소재, 컬러, 가격 등 페이지 텍스트 기반 설명
- 원문 상품 페이지 링크

이미지 픽셀을 분석해 색상, 소재, 실루엣을 추론하지 않는다.

### 신뢰도

- 높음: DataLab 수치와 독립 웹 출처 2개 이상이 일치
- 중간: 독립 웹 출처 2개 이상이 일치
- 낮음: 단일 출처 또는 간접 근거

신뢰도는 예측 확률이 아니다.

## 10. 기본 브랜드 세트

세트 이름: `cashmere-reference`

아래 값은 사용자가 제공한 seed data다. 첫 실행에서 URL 접근 가능 여부, canonical URL, 채널 유형을 검증한다.

| 브랜드 | URL | 채널 | 추적 목적 |
|---|---|---|---|
| guestinresidence | https://guestinresidence.com/ | 공식몰 | Young & Trendy 캐시미어 디자인 |
| Extreme cashmere | https://extreme-cashmere.com/ | 공식몰 | 컬러 조합 |
| &Daughter | https://www.and-daughter.com/ | 공식몰 | 룩북, 브랜드 컨셉, 브루클린 감성 |
| Lisa Yang | https://us.lisa-yang.com/ | 공식몰 | 아시아 고객 선호 가능 디자인 |
| Arch4 | https://www.arch4.co.uk/ | 공식몰 | 베이직과 차별화된 디테일 |
| Le Cashmere | https://www.kolonmall.com/Brands/LECASHMERE | 유통몰 | 룩북 컬러 조합 |
| Iris Von Arnim | https://irisvonarnim.com/us/ | 공식몰 | Brushed Cashmere 라인 |
| LE17 SEPTEMBRE | https://en.le17septembre.com/ | 공식몰 | 베이직과 차별화된 디테일 |
| Quince | https://www.quince.com/women/cashmere | 공식몰 | 소재와 기본 아이템 구성 |
| cashmereinlove | https://www.cashmereinlove.com/ | 공식몰 | 브라렛, 레깅스 등 독특한 아이템 |
| COS | https://www.cos.com/en-us/women/knitwear | 공식몰 | 다양한 니트웨어 아이디어 |
| PLUSH’MERE | https://www.instagram.com/plushmere/?hl=en | Instagram | Colorblock 스타일 |

PLUSH’MERE Instagram은 자동 수집하지 않는다. 사용자가 공개 게시물 URL을 직접 제공하면 참고 링크로 저장하며, 로그인이나 자동 스크롤이 필요하면 수집 실패로 기록한다.

따라서 기본 세트 수용 기준은 자동 수집 후보 11개와 `reference_only` 1개다. PLUSH’MERE를 자동 수집 성공 대상으로 계산하지 않고 `SNS 자동 수집 제외` 사유를 표시한다.

## 11. 데이터 모델

### 주요 테이블

- `brand_sets`
- `brands`
- `brand_set_members`
- `sources`
- `analysis_requests`
- `runs`
- `collection_plans`
- `plan_versions`
- `collection_tasks`
- `source_fetches`
- `products`
- `product_observations`
- `evidence`
- `audit_results`
- `claims`
- `claim_evidence`
- `reports`
- `run_events`

### Graph DB 확장 준비

MVP에서 Graph DB를 사용하지 않는다. 다음 원칙만 지킨다.

- 모든 주요 엔터티에 안정적인 UUID 사용
- 브랜드, 출처, 상품 관찰, 근거, 주장, 보고서를 분리
- 주장과 근거를 `claim_evidence` 관계로 명시
- 저장소 접근을 repository interface로 격리
- 관계 정보가 Markdown 본문에만 존재하지 않게 저장
- 모든 관찰, 근거, 주장, 보고서에 `run_id` 저장
- 생성 skill, 모델, prompt/schema version 저장
- 상품의 영속 identity와 실행 시점별 `product_observation` 분리
- `canonical_url + content_hash + run_id`를 source fetch 중복 방지 키로 사용

향후 `Brand → ProductObservation → Evidence → Claim → Report` 관계를 Graph DB로 투영할 수 있다.

## 12. 내부 API

```text
POST /analyses
GET  /analyses/{analysis_id}
POST /analyses/{analysis_id}/plan
POST /runs/{run_id}/plan-revisions
POST /runs/{run_id}/approve
POST /runs/{run_id}/cancel
GET  /runs/{run_id}
GET  /reports/{report_id}
POST /analyses/{analysis_id}/rerun
```

Hermes tool은 내부 API 또는 명시적 애플리케이션 서비스 인터페이스만 호출한다. DB 파일을 직접 수정하지 않는다.

내부 API는 서비스 토큰으로 인증하고 외부 네트워크에 공개하지 않는다. Discord 요청은 허용된 서버, 채널, 사용자 ID와 연결된 경우에만 실행을 생성한다.

`approve` 요청은 `plan_version`, `plan_hash`, `idempotency_key`를 필수로 받는다. `plan-revisions`는 수정 지시와 현재 버전을 받고 새 버전을 반환한다.

## 13. 오류 처리

- NAVER 인증 실패: 부분 실패로 표시하고 정량 검증 누락을 명시한다.
- NAVER 429: 최대 두 번 제한된 backoff 후 한도 초과로 기록한다.
- 웹 검색 실패: 등록 URL과 DataLab 근거로 계속 진행한다.
- Crawl4AI 실패: Browser Use로 한 번 재시도한다.
- Browser Use 실패: URL과 오류 유형을 기록한다.
- 게시일 부재: 수집일과 분리해 `게시일 확인 불가`로 저장한다.
- 상충 자료: 양쪽 근거와 차이를 함께 표시한다.
- LLM 스키마 오류: 원문을 보존하고 수정 요청을 한 번 수행한다.
- 로컬 LLM 불확실: Discord 사용자 확인으로 전환한다.
- 근거 부족: 추천을 만들지 않고 추가 조사 필요로 표시한다.
- Hermes 재시작: SQLite의 마지막 실행 상태에서 안전하게 재개하거나 실패로 종료한다.
- deadline 또는 일부 공급자 실패: 경고와 실패 이유를 누적하고 렌더링 후 `partial_failed`로 판정한다.

외부 API 호출과 저장 쓰기는 가능한 한 멱등하게 설계한다. 동일 실행의 재시도로 중복 근거와 중복 보고서를 만들지 않는다.

## 14. 안전과 준수

- 공개 URL만 수집한다.
- robots.txt와 사이트 이용약관을 존중한다.
- 로그인, CAPTCHA 우회, 차단 회피를 하지 않는다.
- Browser Use는 실행별 도메인 allowlist를 적용한다.
- 웹 콘텐츠, Discord 메시지, MCP 응답은 비신뢰 입력으로 취급한다.
- URL credentials와 `http/https` 외 scheme을 거부하고 80·443 포트만 허용한다.
- 최초 요청과 모든 DNS 재해석·redirect hop에서 IPv4·IPv6 public IP 여부를 다시 검증한다.
- loopback, private, link-local, multicast, reserved, cloud metadata 주소를 차단한다.
- redirect 수, 응답 byte, 허용 MIME을 제한하고 collector/browser egress firewall로 사설망 접근을 막는다.
- 수집 텍스트를 data-only 구역으로 LLM에 전달하며 웹 콘텐츠가 tool argument나 정책을 만들지 못하게 한다.
- HTML은 sanitizer와 CSP를 적용하고 `javascript:` URL, script, event handler, 위험 SVG를 제거한다.
- Discord 출력에서 mention과 Markdown 제어 문자를 escape한다.
- 썸네일은 동일 SSRF·MIME·크기 검사를 적용한 이미지 proxy를 통해 제공한다.
- Hermes 전체 프로세스를 Docker로 격리한다.
- host terminal backend를 운영 기본값으로 사용하지 않는다.
- API 키를 환경 변수 또는 비밀 저장소에 두고 로그와 보고서에서 제거한다.
- Hermes 하위 프로세스에는 필요한 키만 전달한다.
- 수집 원문 전체와 원본 이미지를 재배포하지 않는다.
- 자동 생성 skill이 운영 워크플로우를 검토 없이 변경하지 못하게 한다.

## 15. 테스트 전략

### 단위 테스트

- Discord 자연어 입력 구조화
- 분석 요청 검증
- 브랜드·URL 정규화와 중복 제거
- URL 안전 정책과 내부 주소 차단
- 수집 계획 스키마
- 코드 정책 검증
- 로컬 LLM validator 결과 스키마
- NAVER 응답 정규화
- Search Trend와 Shopping Insight 연령 코드 변환
- rate limit과 429 backoff
- Crawl4AI 품질 판정
- Browser Use fallback 조건
- 근거 중복 제거
- 주장과 근거 연결
- Markdown·HTML 렌더링

### 통합 테스트

- Discord 입력부터 계획 승인까지
- 모의 NAVER 응답을 사용한 전체 실행
- 고정 HTML fixture를 사용한 Crawl4AI 수집
- Crawl4AI 실패 후 Browser Use fallback
- 근거 부족 후 보완 수집 한 번
- 보완 후에도 부족할 때 경고 생성
- Hermes 재시작 후 실행 상태 복구
- 동일 조건 재실행 시 별도 run 생성
- 계획 수정 후 새 버전 재검증
- stale·중복 승인 409
- 승인 timeout과 취소 전파
- 허용되지 않은 상태 전이 409
- 누적 예산 원자적 차감
- redirect 기반 SSRF와 DNS rebinding 차단
- HTML XSS와 Discord mention escape
- wall-clock deadline 이후 `partial_failed`

### 수용 테스트

결정적 수용 테스트는 고정 NAVER, Tavily, HTML, LLM fixture와 가짜 clock/rate limiter를 사용한다. Hermes adapter와 provider를 주입 가능하게 만들고 외부 네트워크를 사용하지 않는다.

기본 시나리오는 `cashmere-reference` 브랜드 세트, 여성 니트웨어, 한국 여성 25~39세, 20만~70만원, 최근 8주다. 충분 근거, 부족 근거, 계획 수정, stale 승인, 취소, quota, SSRF redirect, XSS, deadline 시나리오를 각각 판정한다.

실제 외부 서비스 연결은 별도 opt-in live smoke test로 실행하며 결정적 수용 테스트의 통과 조건에 포함하지 않는다.

## 16. 성공 기준

- Discord에서 브랜드 세트와 분석 조건을 입력할 수 있다.
- Hermes가 구조화된 수집 계획을 제시한다.
- 사용자가 계획을 승인하거나 수정할 수 있다.
- 정책 한도를 벗어난 계획은 실행되지 않는다.
- 자동 수집 후보 11개와 reference-only 브랜드 1개를 정책에 맞게 처리한다.
- Search Trend 또는 Shopping Insight 신호가 하나 이상 포함되거나 누락 이유가 표시된다.
- 모든 주요 주장과 추천 액션에 근거가 연결된다.
- 충분한 근거 fixture의 `completed` 실행은 근거가 연결된 MD 액션을 세 개 이상 제공한다.
- 근거 부족 fixture의 `partial_failed` 실행은 근거 없는 액션을 만들지 않고 `추가 조사 필요`를 표시한다.
- 수집 실패 URL과 원인이 표시된다.
- 출처 연결 썸네일과 텍스트 설명이 제공된다.
- 근거 보완 루프는 최대 한 번만 실행된다.
- 기본 실행은 15분 이내 완료된다.
- 동일 조건으로 수동 재실행할 수 있다.
- Markdown과 HTML 보고서가 생성된다.

## 17. 향후 확장

MVP 검증 후 다음을 별도 설계한다.

- 예약 실행과 자동 변경 감지
- Graph DB와 관계 탐색
- 이미지 임베딩과 멀티모달 분석
- Instagram 등 인증 소스의 공식 연동
- 자사 판매·재고 데이터
- PDF와 PowerPoint
- 팀·조직 권한
- 통계적 수요예측

이 확장 기능은 MVP 완료 조건이 아니다.

## 18. 공식 참고 문서

- Hermes Agent: https://github.com/NousResearch/hermes-agent
- Hermes 보안 정책: https://github.com/NousResearch/hermes-agent/security
- NAVER API HUB 개요: https://api.ncloud-docs.com/docs/naver-api-hub-overview
- NAVER API HUB 사용 가이드: https://guide.ncloud-docs.com/docs/apihub-overview
- Search Trend: https://api.ncloud-docs.com/docs/naver-api-hub-search-trend
- Shopping Insight 분야별: https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-categories
- Shopping Insight 키워드별: https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-keywords
- Crawl4AI: https://github.com/unclecode/crawl4ai
- Browser Use: https://github.com/browser-use/browser-use

