# 캐시미어·니트웨어 MD 트렌드 에이전트 명세 v3 — 코퍼스 우선 파이프라인

## 1. 문서 상태

- 상태: 2026-07-23 설계 확정, 구현 전.
- 이 문서는 SPEC_V2의 **전면 개정판**이다. 단, V2 전체를 다시 쓰지 않는다.
  파이프라인 구조·설계 원칙·Hermes 역할·저장·마일스톤은 이 문서가 규범이고,
  데이터 계약·소스 레지스트리·수집 사다리·정규화·evidence 정책·예산·안전 정책은
  V2 해당 절이 계속 규범이다. §16 매핑 표가 절 단위로 판정한다.
- 시각 계약은 `DESIGN.md`(Report HTML Design Contract)가 별도 규범 문서로 유지된다.
  이 문서는 이를 참조만 하고 흡수하지 않는다.

### 1.1 V2 대비 핵심 변화 한 줄 요약

LLM이 파이프라인 **말단 요약 전용**(V2 §4.3, §4.6, §15.3)에서 **양 끝 두 경계**로 이동한다:
앞단에서 코퍼스(트렌드 키워드셋)를 생성하고, 말단에서 합성한다.
중간의 모든 측정은 결정론 Python 코어가 수행한다.

## 2. 재설계 이유

V2는 코퍼스(검색 키워드·크롤 시드)를 전부 고정 config로 두고 LLM을 말단 요약에만 썼다.
이 구조는 **코퍼스 갭**을 만든다: config에 없는 신조어·신소재·색 이름은 영원히 측정 대상에
들어오지 못한다. 트렌드 탐지 도구가 트렌드 어휘를 갱신하지 못하는 자기모순이다.

2026-07-23 라이브 실측 3건이 방향을 확정했다:

1. **Pinterest keywords/metrics는 코퍼스 소스로 반증됨.** LLM 생성 용어 5/16 히트 vs
   기존 키워드 2/6 히트로 히트율 차이 없음. 원인은 API가 거친 head-term(crochet,
   cardigan, knitwear 5M+)만 반환하고 pointelle, cool blue, cable knit, cashmere 등
   세부 용어에 전부 갭. 양(버킷)만 주고 방향을 못 준다. → 코퍼스 검증 무대는
   **NAVER**(임의 키워드 + 진짜 시계열)로 이동. Pinterest는 category details만 유지.
2. **RSS 자동 에디토리얼은 부분 성공.** WWD `/tag/{term}/feed/`가 유일한 타깃 소스
   (cashmere/knitwear/wool 히트; crochet/sweaters/cardigan은 WWD 태그 어휘가 아니라
   빈 200). 글로시(Vogue/HB/Elle)는 all.xml만 살아있고 섹션 피드는 전부 404 —
   키워드 필터 + 누적이 필수. 한국 매체(어패럴뉴스/패션비즈)는 RSS 패턴 부재(404)
   → 한국어 축은 웹서치가 커버.
3. **공급 실측은 가동 확인.** Shopify IP 차단은 VPN+백오프로 해결, 9몰 2,035개 수집.
   어댑터 자산(Shopify 사다리 + Quince + 코오롱몰 Apollo SSR + Breuninger JSON-LD)은
   모두 유효하며 이 파이프라인의 공급 축으로 그대로 편입된다.

## 3. 설계 원칙 (V2 §4 대체)

V2 §4.1 Evidence first, §4.2 Human approval, §4.4 Partial failure is normal,
§4.5 Coverage before volume, §4.7 Progressive architecture, §4.8 자동수집 우선은
그대로 유지된다. 아래 두 원칙이 §4.3과 §4.6을 대체한다.

### 3.1 결정론 측정 코어 + LLM 두 경계

- **측정은 결정론이다.** fetch, 어댑터 파싱, NAVER/Pinterest 호출, 정규화, 집계,
  merge, 저장, report 렌더링에는 LLM이 없다. 같은 입력이면 같은 출력.
- **LLM은 정확히 두 곳에만 있다.**
  - **LLM#1 (corpus-in)**: 주간 누적 기사 + 웹서치 → 트렌드 키워드셋(KR+EN).
  - **LLM#2 (synthesis-out)**: merge 번들 → 검증/선행/소멸 3분류 + 갭 + 액션.
- **모든 LLM 출력은 근거로 역추적된다.** LLM#1의 각 concept은 원문 기사/웹서치
  결과를 가리켜야 하고, LLM#2의 각 claim은 EvidenceRef(V2 §8.6)를 가져야 한다.
  숫자 주장은 결정론 validator가 번들 원본과 대조한다. 역추적 실패 항목은 폐기.

### 3.2 선행신호는 버그가 아니다

에디토리얼에는 등장하는데 NAVER 수요가 아직 0인 개념은 측정 실패가 아니라
**선행신호**다 — MD가 시장보다 먼저 잡을 수 있는 빈자리. 3분류(§8)의 "선행"이
이를 1급 출력으로 취급한다. 이 원칙이 코퍼스 우선 구조의 존재 이유다.

## 4. 파이프라인 아키텍처 (V2 §7 대체)

```
[결정론 측정 코어 = Python]                [LLM 경계 = Hermes 분석 역할]

(daily)  RSS poll + dedup ──→ articles 누적
(weekly) 누적 기사 + 웹서치 ─────────────→ LLM#1 corpus-in
                                              ↓ concepts (KR+EN, 근거 역추적)
         NAVER 시계열 ∥ Pinterest 카테고리 ∥ 공급 실측(11브랜드)
              ↓ 정규화·집계(V2 §13)
         merge 번들 ─────────────────────→ LLM#2 synthesis-out
              ↓                               ↓ claims (검증/선행/소멸+갭+액션)
         validator(숫자 대조) ← ──────────────┘
              ↓
         저장(3테이블) → report v3 렌더(DESIGN.md) → Discord(V2 §20)
```

- 순서가 핵심이다: RSS/웹서치가 **먼저**, LLM#1이 코퍼스를 만들고, 그 코퍼스로
  측정 API를 호출한다. 측정 3축(NAVER/Pinterest/공급)은 병렬.
- 실패 격리: 측정 축 하나가 죽어도 파이프라인은 진행하고 CoverageMetrics
  (V2 §8.7)에 기록한다. LLM#1이 죽으면 직전 주 concepts로 fallback, LLM#2가
  죽으면 측정 결과만으로 부분 report를 낸다(V2 §4.4).

## 5. 수집 cadence

2계층으로 분리한다. **수집은 daily, 분석은 weekly.**

### 5.1 daily — RSS 수집

- 대상: WWD `/tag/{term}/feed/` (초기 term: cashmere, knitwear, wool) +
  글로시 all.xml(Vogue/Harper's Bazaar/Elle) 키워드 필터.
- all.xml은 전 토픽 고volume 롤링 스냅샷이라 니트 기사가 빨리 스크롤 아웃된다
  — daily poll이 신호 손실을 막는다. 태그 피드는 저volume이라 daily가 과하지만
  poll 비용이 사실상 0이므로 통일한다.
- URL 기준 dedup 후 articles 테이블(§9)에 누적. LLM 호출 없음.
- 한국 매체 RSS는 부재 확정 — 한국어 축은 weekly 웹서치가 담당.

### 5.2 weekly — 분석 run

주 1회(요일은 config) 전체 파이프라인 1 run:
웹서치 → LLM#1 → 측정 3축 → merge → LLM#2 → 저장 → report → Discord.
LLM 호출·API 예산이 여기에만 발생한다(V2 §21 준수). concept_weekly(§9)의
시간축과 report의 주간 델타가 이 cadence에 정렬된다.

## 6. 코퍼스 경계 — LLM#1 (신규)

### 6.1 입력

- 최근 주 누적 articles(제목, 매체, URL, 발행일, 매칭 term, 발췌).
- 웹서치 결과(한국어 축 포함, 검색 쿼리는 시드 카테고리 기반).
- 직전 주 concepts 목록(연속성 — 기존 개념의 유지/소멸 판단 재료).

### 6.2 출력 계약

concept 목록. 각 항목:

```json
{
  "label_ko": "포인텔 니트",
  "label_en": "pointelle knit",
  "aliases": ["pointelle"],
  "category": "소재|아이템|실루엣|컬러|테마",
  "naver_queries": ["포인텔", "포인텔 니트"],
  "source_refs": ["article:123", "websearch:q4-r2"],
  "rationale": "한 줄 근거"
}
```

### 6.3 검증 규칙 (결정론)

- `source_refs`가 비었거나 실존하지 않는 concept은 폐기하고 로그.
- concept 수 상한은 예산(V2 §21.2)에서 도출. 초과분은 rationale 없이 절단하지
  않고 LLM에 상한을 프롬프트로 명시한다.
- `naver_queries`는 한국어 필수 — NAVER가 검증 무대이기 때문.

## 7. 측정 계층 (V2 §9–§12 유지, 배선만 변경)

측정 3축은 전부 기존 자산이다. 변경은 "고정 config 키워드" → "LLM#1 concepts"로
입력이 바뀌는 배선뿐이다.

- **NAVER (주 무대)**: concepts의 `naver_queries`로 Search Trend 시계열 확보
  (V2 §12). 방향(▲▼→)과 변동%(최근4주/직전4주)의 원천.
- **공급 실측**: 11브랜드 레지스트리(V2 §9) + 수집 사다리(V2 §10). 가동 어댑터:
  Shopify 9몰, Quince, 코오롱몰(Apollo SSR), Breuninger(JSON-LD). SSF/SSG는
  manual_only 유지. 집계는 V2 §13. concepts와의 매칭은 정규화 사전(V2 §13.3)
  기준 결정론 매칭.
- **Pinterest (보조)**: category details의 흐름만 사용. keywords/metrics는
  코퍼스·검증 용도에서 제외(§2 실측 1). 
- **에디토리얼 (V2 §11)**: 이중 역할 — ① M1에서 코퍼스 시드(RSS→LLM#1),
  ② M3에서 트렌드 근거(EditorialEvidence, V2 §8.5/§8.6 그대로).

출력은 merge 번들 하나의 JSON: concepts + 축별 측정치 + CoverageMetrics.

## 8. 합성 경계 — LLM#2 (V2 §15.2 확장)

### 8.1 입력

merge 번들(§7) + 직전 주 concept_weekly 스냅샷.

### 8.2 출력 계약

V2 §8.9 Claim/AnalysisOutput을 유지하되 claim에 3분류 필드를 추가한다:

| 분류 | 판정 재료 | 의미 |
|---|---|---|
| **검증(validated)** | 에디토리얼 히트 + NAVER 수요 상승/유의 | 시장이 이미 반응 — 물량 판단 |
| **선행(leading)** | 에디토리얼 히트 + NAVER 수요 0/미미 | 빈자리 — MD 선점 후보 |
| **소멸(fading)** | 직전 주 존재 + 에디토리얼 퇴장 + 수요 하락 | 축소/정리 후보 |

추가로: 수요–공급 갭(수요 상승인데 11브랜드 공급 희박 = 기회), 액션 제안
(V2 §14.3 근거 규칙 준수).

### 8.3 검증 규칙 (결정론)

- 모든 claim은 EvidenceRef 필수 — 없으면 폐기.
- 숫자 주장(변동%, 수요 방향, 공급 수)은 validator가 번들 원본 값과 대조,
  불일치 시 해당 claim 폐기 + 로그.
- 3분류 판정의 경계값(수요 "미미" 기준 등)은 config 상수로 두고 validator가
  분류-근거 정합을 재검한다. LLM은 서술을, 결정론이 판정 정합을 소유한다.

## 9. 저장 (V2 §18 대체)

### 9.1 스키마 — 3테이블

```sql
-- 에디토리얼 원문 누적 (daily 기록)
articles(
  id, source, url UNIQUE, title, published_at, fetched_at,
  matched_terms, excerpt, raw_path
)

-- 코퍼스 개념 (LLM#1 산출, 역추적 가능)
concepts(
  id, label_ko, label_en, aliases, category,
  first_seen_week, status, source_refs
)

-- 개념 주간 시계열 = 선행/소멸 판정의 원천
concept_weekly(
  concept_id, iso_week,
  naver_series, direction, delta_pct,
  supply_count, editorial_count, classification, run_id,
  PRIMARY KEY (concept_id, iso_week)
)
```

### 9.2 주간 델타 규칙

- concept의 **첫 주**: NAVER API 시계열 자체의 기울기(최근4주/직전4주)로 방향 판정.
- **다음 주부터**: 저장된 직전 주 대비 delta.
- 소량 베이스(직전 평균 < 3)는 △ 캡 — 퍼센트 과장 금지(report v3 규칙과 동일).

### 9.3 driver 추상화

SPEC은 스키마와 인터페이스만 규정한다. 백엔드는 driver 뒤로 추상화:

```
put_article / upsert_concept / append_weekly
get_prior_weeks(concept_id, n) / similar_concepts(label)
```

- 1차 구현: **sqlite** (로컬, 파일 1개, sqlite-vec/FTS5로 유사도 충분).
- 배포 전환 시: pgvector(Supabase/Neon). 스키마 동일(벡터=컬럼 1개), 이관 얕음.
- 로컬/배포 최종 결정은 **미확정** — driver 경계가 결정을 지연 가능하게 만든다.
- RAG/GraphRAG는 채택하지 않는다: 볼륨이 작고(연 1–2K 문서), 누적의 본질이
  그래프가 아니라 시계열이다. `similar_concepts`는 개념 중복 방지용 유사도 조회일
  뿐 검색 증강이 아니다.

## 10. Report와 전달

- **report v3**: 흐름 중심 8축(아이템 흐름/경쟁 브랜드/소재/Pinterest 카테고리/
  수요-공급 갭/트렌드 근거/액션/신뢰도), 신호마다 방향 화살표 + 변동% + 스파크라인.
  시각 규범은 `DESIGN.md`. 프로토(`scratchpad/report_v3.py`)를 `poc/report_html.py`에
  본배선하는 것이 M5.
- **Report Quality Contract**: V2 §17 invariant 전부 유지(빈 데이터/부분 실패 상태 포함).
- **전달: Discord 유지** (V2 §20 메시지 계약 그대로). 발송 cadence만 weekly run에
  정렬. Notion/Slack은 채택하지 않는다.

## 11. Hermes 역할 (V2 §15 대체)

- Hermes의 분석 역할 = **LLM 경계 2곳(LLM#1, LLM#2)의 소유자**. 측정 로직은
  일절 갖지 않는다(V2 §4.6 "Thin Hermes"의 v3 형태).
- **Phase 0 (현재)**: Python이 SDK로 두 경계를 직접 호출. Hermes 미개입.
- **Phase 1**: Hermes가 두 경계를 인수. Python 측정 코어는 무변경.
- 이관 seam은 인터페이스 계약이다:
  - LLM#1: 기사+웹서치 번들 JSON in → 검증된 concepts JSON out (§6).
  - LLM#2: merge 번들 JSON in → 검증된 claims JSON out (§8).
  - 두 계약이 안정적이면 호출 주체 교체는 배선 작업일 뿐이다.

## 12. 마일스톤 (V2 §6/§25/§26 대체)

| M | 이름 | 내용 | 수용 기준 |
|---|---|---|---|
| **M1** | Corpus spine | RSS fetcher(daily poll+dedup+누적) + 웹서치 + LLM#1 인터페이스 | fixture 기사→concepts JSON; 전 concept이 source_refs 역추적 성공; 라이브 run에서 한국어 naver_queries 포함 concepts 산출 |
| **M2** | 수요+공급 측정 | concepts→NAVER 시계열 ∥ Pinterest 카테고리 ∥ 공급 어댑터 배선 + merge 번들 (+페이지네이션 fix: quince 30/288, kolonmall 60/69) | 번들 스키마 검증 통과; 축 1개 실패 시에도 번들 생성 + CoverageMetrics 기록 |
| **M3** | Synthesis | LLM#2 + validator + golden fixture | 3분류 출력; 전 claim EvidenceRef 보유; 숫자 claim validator 대조 통과; 라이브 run 1회 성공 |
| **M4** | 저장+주간 델타 | 3테이블 + sqlite driver + 델타 규칙 | 2주 연속 run에서 델타 산출; 동일 주 재실행 멱등(dedup) |
| **M5** | Report+전달 | report v3 본배선(DESIGN.md) + Discord | V2 §17 invariant 통과; 오너 시각 승인; Discord 발송 성공 |

- 순서는 M1→M5 직렬이 기본이나 M4(저장)는 M2 이후 병행 가능.
- 리스크 집중: **M1·M3 (LLM-in-loop)** — 단위 테스트로 못 막고 라이브 반복 튜닝
  필수. M2/M4는 기존 자산 배선이라 낮음.

## 13. 테스트 전략 (V2 §24 유지 + delta)

V2 §24 전체(단위/fixture/통합/RQC/live smoke)는 유지. v3 추가분:

- **LLM 경계는 green 단위 테스트가 runtime FAIL을 가릴 수 있다** — LLM#1/#2는
  live-verify가 필수 수용 기준이다(마일스톤 표의 "라이브 run" 항목).
- LLM#1/#2 각각 golden fixture(입력 번들 → 기대 출력 형태)로 계약 회귀를 잡고,
  내용 품질은 라이브 튜닝으로 잡는다. 둘을 혼동하지 않는다.
- validator(§6.3, §8.3)는 순수 결정론이므로 일반 단위 테스트 대상.

## 14. 제외 범위 (v3에서 명시적으로 하지 않는 것)

- RAG/GraphRAG 저장·검색 증강 (§9.3 근거).
- Pinterest keywords/metrics의 코퍼스·검증 용도 (§2 실측 1).
- 한국 매체 RSS 수집 (패턴 부재 확정 — 웹서치로 대체).
- Notion/Slack 전달 채널 (Discord 유지).
- report 축 01–08의 시각 재정의 (DESIGN.md 소관).
- pgvector 즉시 도입 (driver 뒤에 지연).

## 15. 위험

| 위험 | 완화 |
|---|---|
| LLM#1 코퍼스 품질 불안정(과생성/일반어 남발) | source_refs 역추적 강제 + 상한 + 직전 주 concepts fallback |
| NAVER 무응답/쿼터 | CoverageMetrics 기록 + 부분 report (V2 §4.4) |
| RSS 소스 사멸(WWD 태그 피드 변경 등) | daily poll이 조기 감지; 소스별 연속 빈 응답 로그 경보 |
| Shopify IP 재차단 | VPN+백오프 절차 문서화됨; 실패 시 해당 축 CoverageMetrics 격리 |
| LLM#2 분류-근거 불일치 | validator 정합 재검(§8.3) — 서술은 LLM, 판정 정합은 결정론 |
| 스키마 조기 고착 | driver 인터페이스 뒤 백엔드 교체 가능; 스키마는 양 백엔드 동일 설계 |

## 16. V2 절 매핑 표

| V2 절 | v3 판정 |
|---|---|
| §1–§3 (문서 상태/비전/제품 계층) | 유지 (마일스톤 명칭 §1.3만 §12로 대체) |
| §4 설계 원칙 | **대체** — §4.3, §4.6을 v3 §3이 재정의, 나머지 유지 |
| §5 사용자·시나리오 | 유지 |
| §6 단계별 범위 | **대체** — v3 §12 (M1–M5) |
| §7 목표 아키텍처 | **대체** — v3 §4 |
| §8 데이터 계약 | 유지 + v3 §6.2/§8.2가 LLM 경계 계약 추가 |
| §9–§12 (레지스트리/사다리/에디토리얼/NAVER) | 유지 — 배선만 v3 §7 |
| §13 정규화·집계 | 유지 |
| §14 Evidence 정책 | 유지 |
| §15 Hermes 역할 | **대체** — v3 §11 |
| §16 모순 감사 | 유지 (v3 반영 재감사는 구현 중 갱신) |
| §17 Report Quality Contract | 유지 |
| §18 Run bundle·저장 | **대체** — v3 §9 |
| §19 실행 상태 | **폐기** — stale, v3 §12가 현재 상태 |
| §20 Discord | 유지 — cadence만 weekly 정렬 |
| §21 예산 | 유지 — LLM 호출은 weekly run에만 발생 |
| §22 안전·정책 | 유지 |
| §23 오류 처리 | 유지 |
| §24 테스트 전략 | 유지 + v3 §13 delta |
| §25 수용 기준 / §26 구현 순서 | **대체** — v3 §12 |
| §27 제외 범위 | 유지 + v3 §14 추가 |
| §28 위험 | 유지 + v3 §15 추가 |
| §29–§30 | 유지 |

## 17. 참고 문서

- `SPEC_V2.md` — 유지 절의 규범 원문.
- `DESIGN.md` — Report HTML 시각 계약.
- `POC_SPEC.md` — PoC 이력 (§12 재설계 합의 포함).
- `out/report.html`, `out/report_v3.html` — 시각 레퍼런스.
