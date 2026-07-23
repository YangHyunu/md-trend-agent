# M2 수요+공급 측정 + 머지 번들 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SPEC_V3 §12 M2 — LLM#1 concepts를 입력으로 측정 3축(NAVER 시계열 ∥ Pinterest 카테고리 ∥ 공급 어댑터)을 배선하고 머지 번들(concepts + 축별 측정치 + CoverageMetrics)을 산출한다. + quince 페이지네이션 커버리지 fix + M1 최종리뷰 이관분.

**Architecture:** M2는 **LLM 호출이 0인 순수 결정론 계층**이다(SPEC_V3 §3.1 — LLM은 M1의 LLM#1과 M3의 LLM#2 뿐). 기존 자산 재사용이 원칙: NAVER 클라이언트(`poc/naver.py`)에 concept 배치 호출만 추가, Pinterest(`poc/pinterest.py`)에 카테고리 단독 fetch만 추가, 공급은 `datalayer.extract.extract_all` 그대로. 신규 모듈은 `poc/measure.py`(델타/방향 수학 + concept↔공급 매칭), `poc/bundle.py`(머지 번들 pydantic 스키마 + 조립), `poc/weekly.py`(주간 오케스트레이션 CLI). `poc/run.py`(report v2 파이프라인)는 **무변경** — report 재배선은 M5.

**Tech Stack:** Python ≥3.11, httpx, pydantic v2, pytest + httpx.MockTransport. 신규 의존성 없음.

## Global Constraints

- Python ≥3.11, HTTP는 httpx만(requests 금지). 신규 의존성 추가 금지.
- **M2 전 코드에 LLM 호출 금지**(SPEC_V3 §3.1). `anthropic` import가 새 모듈에 나타나면 플랜 위반.
- NAVER Search Trend 한도: 요청당 keywordGroups ≤5, 그룹당 keywords ≤20 (`poc/naver.py:126` `_offline_check` 기존 assert 준수). ages=`config.SEARCH_TREND_AGES`(["4","5","6"]), gender="f", timeUnit="week" — 기존 builder와 동일.
- concept ref 문법(SPEC_V3 §6.2, M1 확정): 기사 ref = `a` + sha1(url) 앞 10 hex (`poc/rss.py` 계약), 웹서치 ref = `w{i}` (crawl_results 인덱스).
- 부분 실패는 정상(V2 §4.4): 축 하나가 죽어도 번들은 생성되고 CoverageMetrics에 기록된다. ratio는 분모 0이면 `None`이며 0%로 표현하지 않는다(V2 §8.7).
- 경계값은 config 상수(SPEC_V3 §8.3): 소량 베이스 캡 `직전4주 평균 < 3`(SPEC_V3 §9.2 명문), flat 밴드 ±10%(신규 상수 — 오너 튜닝 가능).
- 테스트 네트워크 금지: httpx.MockTransport + 모듈 레벨 헬퍼(`tests/datalayer/test_shopify.py` 관례, `@pytest.fixture` 데코레이터 미사용 — pytest 내장 `monkeypatch` 인자는 허용, `tests/poc/test_corpus.py` 선례). 시작 시점 스위트 158 pass — 각 태스크 후에도 전체 green 유지.
- 커밋 스타일: `feat(poc)|fix(poc)|feat(datalayer): 한국어 요약 (SPEC_V3 §N)` + trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- 2026-07-23 라이브 실측(이 플랜 작성 중 확인, 재검증 불필요):
  - quince: SSR이 `cursor`/`page`/`offset` 쿼리와 `/_next/data/` 라우트 파라미터를 전부 무시(클라이언트 XHR 페이지네이션, 엔드포인트는 정적 HTML에 미노출). sitemap_subcollections.xml의 women-cashmere 하위 컬렉션 12경로 유니온으로 unique 30→107 확보(전체 290 — 잔여는 XHR API 필요, 미채택).
  - kolonmall: SSR 항상 1페이지(60/69). 클라이언트 페이지네이션은 robots가 Disallow한 `/graphql` 경유 — **우회하지 않는다**(어댑터 docstring 정책 유지). 60/69는 정책 한계로 CoverageMetrics에 정직 기록.
- `out/weekly/2026-W30.json`은 report v3 스크래치패드 프로토 산출물 — 덮어쓰지 않는다. M2 아카이브는 `merge_bundle_` 접두 사용.

---

### Task 1: M1 최종리뷰 이관 픽스 (corpus/rss)

**Files:**
- Modify: `poc/corpus.py:34-56` (validate_concepts), `poc/corpus.py:65` (build_corpus_input docstring), `poc/corpus.py:163-164` (`__main__`)
- Modify: `poc/rss.py:140-141` (`__main__`)
- Test: `tests/poc/test_corpus.py`, `tests/poc/test_rss.py`

**Interfaces:**
- Consumes: 기존 `validate_concepts(output, valid_refs, max_concepts)`, `poll()`, `main()`.
- Produces: `corpus.exit_code(result: dict) -> int`, `rss.exit_code(result: dict) -> int` — Task 8의 cron 배선이 이 패턴을 따른다. `validate_concepts`의 `max_concepts=0` 의미 변경(0도 유효한 상한).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_corpus.py`에 추가 (기존 import 유지, 파일 끝에):

```python
def test_validate_concepts_honors_zero_max():
    # `max_concepts or DEFAULT`는 0을 default로 삼킨다 — is None으로 교정 확인
    out = CorpusOutput(concepts=[_concept()])
    kept, dropped = validate_concepts(out, {"a0000000001"}, max_concepts=0)
    assert kept == []
    assert dropped == [{"label_ko": _concept().label_ko, "reason": "over_max_concepts"}]


def test_corpus_exit_code():
    from poc.corpus import exit_code
    assert exit_code({"concepts": 16, "dropped": 0}) == 0
    assert exit_code({"concepts": 16, "dropped": 0, "fallback": "APIError: x"}) == 1
    assert exit_code({"concepts": 0, "dropped": 5, "fallback": "all_concepts_dropped"}) == 1
```

주의: `_concept()`는 `tests/poc/test_corpus.py`에 이미 있는 Concept 생성 헬퍼를 쓴다. 없거나 dict를 반환하면 파일 상단 헬퍼에 맞춰 위 코드를 조정한다(Concept pydantic 인스턴스 필요).

`tests/poc/test_rss.py` 끝에 추가:

```python
def test_rss_exit_code():
    from poc.rss import exit_code
    assert exit_code({"fetched": 5, "added": 2, "failures": []}) == 0
    # 부분 실패는 정상(V2 §4.4) — 일부 피드만 죽으면 0
    assert exit_code({"fetched": 3, "added": 1, "failures": [{"feed": "wwd:wool"}]}) == 0
    # 전 피드 실패만 경보
    assert exit_code({"fetched": 0, "added": 0, "failures": [{"feed": "all"}]}) == 1
    # 조용한 주(피드 정상, 새 글 없음)는 정상
    assert exit_code({"fetched": 0, "added": 0, "failures": []}) == 0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py tests/poc/test_rss.py -v`
Expected: 신규 3개 테스트 FAIL (`ImportError: cannot import name 'exit_code'` / zero-max assert 실패), 기존 테스트 PASS.

- [ ] **Step 3: 구현**

`poc/corpus.py:39` 교체:

```python
    if max_concepts is None:
        max_concepts = config.MAX_CONCEPTS
```

`poc/corpus.py` `build_corpus_input` docstring 추가 (함수 시그니처 바로 아래):

```python
    """기사+웹서치+직전 concepts → LLM#1 입력 번들과 유효 ref 집합.

    ref 문법(SPEC_V3 §6.2): 기사 = `a`+sha1(url)[:10] (rss.py가 부여한 id 그대로),
    웹서치 = `w{i}` (crawl_results 통과 항목의 enumerate 인덱스 — M4에서 안정 id로 교체 예정).
    """
```

`poc/corpus.py` 끝부분, `main` 아래에 추가 + `__main__` 교체:

```python
def exit_code(result: dict) -> int:
    """cron 경보용(SPEC_V3 §15): fallback(LLM 실패·전량폐기)은 1 — 직전 주 유지를 은폐하지 않는다."""
    return 1 if "fallback" in result else 0


if __name__ == "__main__":
    _result = main()
    print(json.dumps(_result, ensure_ascii=False))
    raise SystemExit(exit_code(_result))
```

`poc/rss.py` 끝부분 교체:

```python
def exit_code(result: dict) -> int:
    """cron 경보용(SPEC_V3 §15): 전 피드 실패(fetched 0 + failures)만 1 — 부분 실패는 정상(V2 §4.4)."""
    return 1 if result["fetched"] == 0 and result["failures"] else 0


if __name__ == "__main__":
    _result = poll()
    print(json.dumps(_result, ensure_ascii=False))
    raise SystemExit(exit_code(_result))
```

- [ ] **Step 4: 테스트 통과 + 전체 스위트 확인**

Run: `.venv/bin/pytest -q`
Expected: 158 + 3 = 161 passed (기존 카운트 기준 — 정확 수치는 출력 따름, 실패 0이 기준).

- [ ] **Step 5: 커밋**

```bash
git add poc/corpus.py poc/rss.py tests/poc/test_corpus.py tests/poc/test_rss.py
git commit -m "fix(poc): M1 이관 — max_concepts is None·ref 문법 주석·CLI exit code (SPEC_V3 §6, §15)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Quince 커버리지 — 서브컬렉션 유니온 (30→107)

**Files:**
- Modify: `datalayer/sources/quince.py:27` (`_DEFAULT_PATHS`)
- Test: `tests/datalayer/test_quince.py`

**Interfaces:**
- Consumes: `QuinceSource(collection_paths)` 기존 시그니처 — productId 기준 경로 간 dedup은 `fetch`에 이미 구현됨(`records` dict), 경로별 silent-cap 경고 로그도 기존 유지.
- Produces: 확장된 `_DEFAULT_PATHS` 12경로. `QuinceSource()` 무인자 사용처(`datalayer/extract.py:28`)가 자동으로 새 경로를 탄다 — extract.py 수정 없음.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/datalayer/test_quince.py` 끝에 추가:

```python
def test_default_paths_are_subcollection_union():
    # 2026-07-23 실측: SSR은 페이지네이션 쿼리 무시 → sitemap 하위 컬렉션 유니온이 유일한 커버리지 경로
    from datalayer.sources.quince import _DEFAULT_PATHS
    assert _DEFAULT_PATHS[0] == "shop/women/cashmere"          # 루트 유지
    assert len(_DEFAULT_PATHS) == 12
    assert len(set(_DEFAULT_PATHS)) == 12                       # 중복 없음
    assert "shop/women/sweaters-&-jackets/cashmere" in _DEFAULT_PATHS


def test_default_paths_survive_dead_subcollections():
    # 하위 컬렉션이 404로 죽어도(사이트 개편) 루트만 살아있으면 수집은 성공해야 한다
    with quince_client() as c:   # 핸들러는 루트만 200, 나머지 404
        recs = QuinceSource().fetch("Quince", "https://www.quince.com/", c)
    assert recs is not None and len(recs) == 3
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/datalayer/test_quince.py -v`
Expected: `test_default_paths_are_subcollection_union` FAIL (`len 1 != 12`), 나머지 PASS (`survive_dead` 는 현행 단일 경로에서도 통과할 수 있음 — 회귀 가드로 유지).

- [ ] **Step 3: 구현**

`datalayer/sources/quince.py:27` `_DEFAULT_PATHS` 교체:

```python
# 2026-07-23 실측: SSR은 cursor/page/offset 쿼리와 /_next/data 라우트를 전부 무시
# (클라이언트 XHR 페이지네이션, 엔드포인트 정적 미노출). sitemap_subcollections.xml의
# women-cashmere 하위 컬렉션 유니온으로 unique 30→107 확보(전체 290 — 잔여는 XHR API
# 필요, 미채택). 경로 간 productId dedup은 fetch의 records dict가 수행.
_DEFAULT_PATHS = [
    "shop/women/cashmere",
    "shop/women/cashmere/accessories",
    "shop/women/cashmere/dresses",
    "shop/women/cashmere/hats",
    "shop/women/cashmere/outerwear",
    "shop/women/cashmere/scarves-gloves",
    "shop/women/cashmere/sweats",
    "shop/women/cashmere/throws-blankets",
    "shop/women/sweaters-&-jackets/cashmere",
    "shop/women/sweaters-&-jackets/cashmere-collection",
    "shop/women/sweaters-&-jackets/cashmere/cotton-sweaters",
    "shop/women/sweaters-&-jackets/cashmere/merino-wool-sweaters",
]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/pytest tests/datalayer/test_quince.py -q`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add datalayer/sources/quince.py tests/datalayer/test_quince.py
git commit -m "feat(datalayer): quince 서브컬렉션 유니온 — SSR 30개 한계를 12경로 dedup으로 30→107 (SPEC_V3 §12 M2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

참고(코드 변경 아님): kolonmall 60/69는 robots Disallow(`/graphql`) 정책 한계로 확정 — 이 플랜에서 우회하지 않으며, Task 7의 CoverageMetrics가 기존 경고 로그와 함께 정직 기록한다.

---

### Task 3: concepts → NAVER 시계열 배선

**Files:**
- Modify: `poc/config.py` (상수 추가), `poc/naver.py` (함수 2개 추가)
- Create: `tests/poc/test_naver_concepts.py`

**Interfaces:**
- Consumes: `config.SEARCH_TREND_AGES`, `config.period()`, `naver._normalize(raw, source, coverage_mismatch)` — 기존 그대로.
- Produces:
  - `config.MAX_CONCEPT_TREND_CALLS: int = 4`
  - `build_concept_trend_payload(concepts: list[dict], start: str, end: str) -> dict` — concepts ≤5개 배치 1개분 payload.
  - `fetch_concept_trends(concepts: list[dict], client: httpx.Client | None = None) -> dict` — 반환 `{"raw": {call_name: raw}, "signals": [...], "failures": [...]}` (fetch_all과 동일 계약). signal의 `group` = concept `label_ko`, `source` = `"concept_trend"`. Task 7 조립이 `signals`의 `group`으로 concept과 조인한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_naver_concepts.py` 생성:

```python
"""concepts→NAVER Search Trend 배치 배선 테스트 (SPEC_V3 §7). 네트워크 없음."""
import json

import httpx

from poc import config
from poc.naver import build_concept_trend_payload, fetch_concept_trends


def _concept(i: int) -> dict:
    return {"label_ko": f"컨셉{i}", "label_en": f"concept {i}",
            "naver_queries": [f"쿼리{i}"], "aliases": [], "category": "테마",
            "source_refs": ["a0000000001"], "rationale": "r"}


def _echo_handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    results = [{"title": g["groupName"], "data": [{"period": "2026-06-01", "ratio": 50.0}]}
               for g in payload["keywordGroups"]]
    return httpx.Response(200, json={"results": results})


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url=config.NAVER_BASE_URL)


def test_payload_respects_naver_limits():
    p = build_concept_trend_payload([_concept(i) for i in range(5)],
                                    "2026-05-25", "2026-07-20")
    assert len(p["keywordGroups"]) <= 5
    assert all(len(g["keywords"]) <= 20 for g in p["keywordGroups"])
    assert p["ages"] == ["4", "5", "6"] and p["gender"] == "f" and p["timeUnit"] == "week"
    assert p["keywordGroups"][0] == {"groupName": "컨셉0", "keywords": ["쿼리0"]}


def test_fetch_batches_of_five(monkeypatch):
    monkeypatch.setenv("NCP_API_HUB_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_API_HUB_CLIENT_SECRET", "secret")
    with _client(_echo_handler) as c:
        res = fetch_concept_trends([_concept(i) for i in range(12)], client=c)
    assert len(res["raw"]) == 3                       # ceil(12/5)
    assert len(res["signals"]) == 12
    assert res["signals"][0]["group"] == "컨셉0"
    assert res["signals"][0]["source"] == "concept_trend"
    assert res["signals"][0]["coverage_mismatch"] is False
    assert res["failures"] == []


def test_fetch_isolates_batch_failure(monkeypatch):
    monkeypatch.setenv("NCP_API_HUB_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_API_HUB_CLIENT_SECRET", "secret")

    def flaky(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["keywordGroups"][0]["groupName"] == "컨셉5":   # 2번째 배치 죽음
            return httpx.Response(500, text="boom")
        return _echo_handler(request)

    with _client(flaky) as c:
        res = fetch_concept_trends([_concept(i) for i in range(12)], client=c)
    assert len(res["signals"]) == 7                   # 배치1(5) + 배치3(2)
    assert len(res["failures"]) == 1
    assert res["failures"][0]["call"] == "concept_trend_b1"


def test_fetch_respects_call_budget(monkeypatch):
    monkeypatch.setenv("NCP_API_HUB_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_API_HUB_CLIENT_SECRET", "secret")
    with _client(_echo_handler) as c:
        res = fetch_concept_trends([_concept(i) for i in range(25)], client=c)
    assert len(res["raw"]) == config.MAX_CONCEPT_TREND_CALLS      # 4번째까지만 호출
    assert any("예산" in f["error"] for f in res["failures"])      # 5번째 배치는 기록


def test_fetch_without_env_returns_failure(monkeypatch):
    monkeypatch.delenv("NCP_API_HUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("NCP_API_HUB_CLIENT_SECRET", raising=False)
    res = fetch_concept_trends([_concept(0)])
    assert res["signals"] == [] and len(res["failures"]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_naver_concepts.py -v`
Expected: 전부 FAIL (`ImportError: cannot import name 'build_concept_trend_payload'`).

- [ ] **Step 3: 구현**

`poc/config.py` 끝(`MAX_CONCEPTS` 다음)에 추가:

```python
# --- M2 concept 측정 (SPEC_V3 §7) ---
MAX_CONCEPT_TREND_CALLS = 4   # concepts ≤20 ÷ 요청당 5그룹 = 4 (V2 §21 weekly 예산)
```

`poc/naver.py`의 `fetch_all` 아래에 추가:

```python
def build_concept_trend_payload(concepts: list[dict], start: str, end: str) -> dict:
    """LLM#1 concepts ≤5개 배치 → Search Trend payload. 그룹=concept, 키워드=naver_queries."""
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "keywordGroups": [
            {"groupName": c["label_ko"], "keywords": c["naver_queries"][:20]}
            for c in concepts
        ],
        "gender": "f",
        "ages": config.SEARCH_TREND_AGES,
    }


def fetch_concept_trends(concepts: list[dict],
                         client: httpx.Client | None = None) -> dict:
    """concepts → NAVER Search Trend 시계열 (SPEC_V3 §7 주 무대). 반환 계약 fetch_all과 동일.

    5개씩 배치, MAX_CONCEPT_TREND_CALLS 초과 배치는 silent 절단 대신 failures에 기록.
    signal.group = label_ko — 머지 번들 조립(poc/bundle.py)의 조인 키.
    """
    client_id = os.environ.get("NCP_API_HUB_CLIENT_ID")
    client_secret = os.environ.get("NCP_API_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"raw": {}, "signals": [], "failures": [
            {"call": "concept_trend", "error": "NCP_API_HUB_CLIENT_ID/SECRET 환경변수 없음"}]}

    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
        "Content-Type": "application/json",
    }
    start, end = config.period()
    result = {"raw": {}, "signals": [], "failures": []}
    batches = [concepts[i:i + 5] for i in range(0, len(concepts), 5)]
    own = client is None
    if own:
        client = httpx.Client(base_url=config.NAVER_BASE_URL, headers=headers, timeout=20)
    else:
        client.headers.update(headers)
    try:
        for i, batch in enumerate(batches):
            name = f"concept_trend_b{i}"
            if i >= config.MAX_CONCEPT_TREND_CALLS:
                result["failures"].append({"call": name, "error": "NAVER 호출 예산 초과로 생략"})
                continue
            try:
                resp = client.post("/search-trend/v1/search",
                                   json=build_concept_trend_payload(batch, start, end))
                resp.raise_for_status()
                raw = resp.json()
                result["raw"][name] = raw
                result["signals"].extend(_normalize(raw, "concept_trend", False))
            except Exception as e:
                result["failures"].append({"call": name, "error": f"{type(e).__name__}: {e}"})
    finally:
        if own:
            client.close()
    return result
```

- [ ] **Step 4: 테스트 통과 + 전체 스위트 확인**

Run: `.venv/bin/pytest tests/poc/test_naver_concepts.py -q && .venv/bin/pytest -q`
Expected: 신규 5개 포함 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add poc/config.py poc/naver.py tests/poc/test_naver_concepts.py
git commit -m "feat(poc): concepts→NAVER 시계열 배치 배선 — 고정 config 키워드 대체 (SPEC_V3 §7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 델타/방향 결정론 수학 (`poc/measure.py` 1/2)

**Files:**
- Modify: `poc/config.py` (경계값 상수)
- Create: `poc/measure.py`
- Create: `tests/poc/test_measure.py`

**Interfaces:**
- Consumes: `config.SMALL_BASE_MEAN`, `config.DELTA_FLAT_BAND_PCT` (이 태스크에서 신설).
- Produces: `series_delta(series: list[dict]) -> dict` — 입력은 NAVER signal의 `series`(`[{"period", "ratio"}]` 오름차순), 반환 `{"delta_pct": float | None, "direction": "up"|"down"|"flat"|"small_base"|"insufficient", "recent_mean": float | None, "prior_mean": float | None}`. Task 7 조립과 M3 validator·M4 `concept_weekly.direction/delta_pct`가 이 값을 그대로 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_measure.py` 생성:

```python
"""결정론 측정 수학 + concept↔공급 매칭 테스트 (SPEC_V3 §7, §9.2). LLM·네트워크 없음."""
from datalayer.records import ProductRecord
from poc.measure import concept_facets, match_supply, series_delta


def _series(ratios: list[float]) -> list[dict]:
    return [{"period": f"2026-06-{i+1:02d}", "ratio": r} for i, r in enumerate(ratios)]


def test_series_delta_up():
    d = series_delta(_series([10, 10, 10, 10, 20, 20, 20, 20]))
    assert d == {"delta_pct": 100.0, "direction": "up",
                 "recent_mean": 20.0, "prior_mean": 10.0}


def test_series_delta_down_and_flat():
    assert series_delta(_series([20, 20, 20, 20, 10, 10, 10, 10]))["direction"] == "down"
    d = series_delta(_series([10, 10, 10, 10, 10.5, 10.5, 10.5, 10.5]))
    assert d["direction"] == "flat" and d["delta_pct"] == 5.0


def test_series_delta_small_base_caps_percent():
    # 직전4주 평균 < 3 → 퍼센트 과장 금지(SPEC_V3 §9.2) — delta_pct 산출 안 함
    d = series_delta(_series([0, 1, 0, 2, 30, 30, 30, 30]))
    assert d["direction"] == "small_base" and d["delta_pct"] is None
    assert d["prior_mean"] == 0.75


def test_series_delta_zero_prior_is_small_base():
    d = series_delta(_series([0, 0, 0, 0, 5, 5, 5, 5]))
    assert d["direction"] == "small_base" and d["delta_pct"] is None


def test_series_delta_insufficient_points():
    # 8포인트 미만 — 판정 불가를 0%로 표현하지 않는다(V2 §8.7 정신)
    d = series_delta(_series([10, 20, 30]))
    assert d == {"delta_pct": None, "direction": "insufficient",
                 "recent_mean": None, "prior_mean": None}
    assert series_delta([])["direction"] == "insufficient"
```

(`concept_facets`/`match_supply` import는 Task 5에서 구현 — 이 시점엔 import 에러가 나므로 **Task 4 동안은 import 줄에서 두 이름을 빼고** Task 5에서 되돌린다.)

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_measure.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'poc.measure'`).

- [ ] **Step 3: 구현**

`poc/config.py` 끝에 추가:

```python
# --- 방향/델타 경계값 (SPEC_V3 §8.3 — 판정 정합은 결정론 소유, §9.2 소량 베이스 캡) ---
DELTA_FLAT_BAND_PCT = 10.0   # |delta| < 10% → flat(→). 오너 튜닝 가능 상수.
SMALL_BASE_MEAN = 3.0        # 직전4주 평균 < 3 → small_base(△), delta_pct 미산출(과장 금지)
```

`poc/measure.py` 생성:

```python
"""결정론 측정 계층 (SPEC_V3 §7, §9.2) — 델타/방향 수학 + concept↔공급 매칭. LLM 없음."""
from poc import config


def series_delta(series: list[dict]) -> dict:
    """주간 series(period 오름차순) → 최근4주 vs 직전4주 델타/방향 (SPEC_V3 §9.2 첫 주 규칙).

    direction: up(▲) / down(▼) / flat(→) / small_base(△) / insufficient.
    - small_base: 직전4주 평균 < config.SMALL_BASE_MEAN — delta_pct 미산출(퍼센트 과장 금지).
    - insufficient: 포인트 < 8 — 판정 불가를 0%로 표현하지 않는다.
    M4의 concept_weekly.direction/delta_pct가 이 값을 그대로 저장한다.
    """
    ratios = [p["ratio"] for p in series]
    if len(ratios) < 8:
        return {"delta_pct": None, "direction": "insufficient",
                "recent_mean": None, "prior_mean": None}
    recent_mean = sum(ratios[-4:]) / 4
    prior_mean = sum(ratios[-8:-4]) / 4
    if prior_mean < config.SMALL_BASE_MEAN:
        return {"delta_pct": None, "direction": "small_base",
                "recent_mean": round(recent_mean, 2), "prior_mean": round(prior_mean, 2)}
    delta = (recent_mean / prior_mean - 1) * 100
    if delta >= config.DELTA_FLAT_BAND_PCT:
        direction = "up"
    elif delta <= -config.DELTA_FLAT_BAND_PCT:
        direction = "down"
    else:
        direction = "flat"
    return {"delta_pct": round(delta, 1), "direction": direction,
            "recent_mean": round(recent_mean, 2), "prior_mean": round(prior_mean, 2)}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_measure.py -q`
Expected: 5 passed.

- [ ] **Step 5: 커밋**

```bash
git add poc/config.py poc/measure.py tests/poc/test_measure.py
git commit -m "feat(poc): 최근4주/직전4주 델타·방향 결정론 — 소량베이스 캡 포함 (SPEC_V3 §9.2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: concept↔공급 결정론 매칭 (`poc/measure.py` 2/2)

**Files:**
- Modify: `poc/measure.py`
- Test: `tests/poc/test_measure.py`

**Interfaces:**
- Consumes: `datalayer.fields.match_item / extract_materials / extract_silhouettes / map_color_family` (V2 §13.3 정규화 사전), `datalayer.records.ProductRecord`.
- Produces:
  - `concept_facets(concept: dict) -> dict` — `{"item": str|None, "materials": list[str], "silhouettes": list[str], "color_family": str|None}`.
  - `match_supply(concept: dict, products: list[ProductRecord]) -> dict` — `{"supply_count": int | None, "facets": dict, "unmeasurable": bool}`. **facet 0개면 `supply_count=None`(측정 불가) — 0(측정됐는데 없음, 수요-공급 갭 신호)과 구분한다.** Task 7 CoverageMetrics의 `concept_match` 축이 unmeasurable을 집계한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_measure.py` import 줄을 되돌리고(`concept_facets, match_supply, series_delta`) 끝에 추가:

```python
def _rec(**kw) -> ProductRecord:
    base = dict(brand="b", url="https://x/p", item=None, colors_raw=[],
                price_native=None, currency=None, compare_at_native=None,
                on_sale=False, materials=[], published_at=None, source="t")
    base.update(kw)
    return ProductRecord(**base)


def _concept(**kw) -> dict:
    base = dict(label_ko="캐시미어 니트", label_en="cashmere knit", aliases=[],
                category="소재", naver_queries=["캐시미어 니트"],
                source_refs=["a0000000001"], rationale="r")
    base.update(kw)
    return base


def test_concept_facets_from_label_and_aliases():
    f = concept_facets(_concept(label_en="cashmere cardigan", aliases=["cardi"]))
    assert f["item"] == "Cardigan" and f["materials"] == ["cashmere"]
    # 'knit'는 ITEM_SYNONYMS에서 의도적으로 제외(기법어) — item은 None, 소재만 잡힘
    f2 = concept_facets(_concept(label_en="cashmere knit"))
    assert f2["item"] is None and f2["materials"] == ["cashmere"]
    # 컬러 concept → 8계열 매핑
    f3 = concept_facets(_concept(label_en="icy blue", category="컬러"))
    assert f3["color_family"] == "블루·네이비"


def test_match_supply_requires_all_facets():
    prods = [
        _rec(item="Cardigan", materials=["cashmere"]),
        _rec(item="Cardigan", materials=["wool"]),
        _rec(item="Sweater", materials=["cashmere"]),
    ]
    m = match_supply(_concept(label_en="cashmere cardigan"), prods)
    assert m["supply_count"] == 1 and m["unmeasurable"] is False


def test_match_supply_material_only_counts_all_items():
    prods = [_rec(item="Sweater", materials=["cashmere"]),
             _rec(item="Dress", materials=["cashmere"]),
             _rec(item="Sweater", materials=["wool"])]
    m = match_supply(_concept(label_en="cashmere knit"), prods)
    assert m["supply_count"] == 2


def test_match_supply_vocab_gap_is_unmeasurable_not_zero():
    # pointelle은 정규화 사전에 없음 → None(측정 불가). 0(공급 갭)과 구분 — 정직 표기
    m = match_supply(_concept(label_en="pointelle knit", label_ko="포인텔 니트",
                              aliases=["pointelle"]), [_rec(item="Sweater")])
    assert m["supply_count"] is None and m["unmeasurable"] is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_measure.py -v`
Expected: 신규 4개 FAIL (`ImportError`), 기존 5개 PASS.

- [ ] **Step 3: 구현**

`poc/measure.py` 끝에 추가 (파일 상단 import에 `from datalayer import fields`, `from datalayer.records import ProductRecord` 추가):

```python
def concept_facets(concept: dict) -> dict:
    """concept 라벨/알리아스 → 정규화 사전 facet (V2 §13.3 결정론 매칭).

    영문 텍스트만 유효 매칭 — 상품 정규화 필드가 영문 canonical이기 때문.
    한국어 alias는 사전에 안 걸려 무해하게 통과한다.
    """
    texts = [concept["label_en"], *concept.get("aliases", [])]
    item = None
    materials: list[str] = []
    silhouettes: list[str] = []
    color_family = None
    for t in texts:
        item = item or fields.match_item(t)
        for m in fields.extract_materials(t):
            if m not in materials:
                materials.append(m)
        for s in fields.extract_silhouettes(t, [], ""):
            if s not in silhouettes:
                silhouettes.append(s)
        color_family = color_family or fields.map_color_family(t)
    return {"item": item, "materials": materials,
            "silhouettes": silhouettes, "color_family": color_family}


def match_supply(concept: dict, products: list[ProductRecord]) -> dict:
    """facet AND 매칭 공급 count. facet 0개 = unmeasurable(None) — 0(공급 갭)과 구분.

    unmeasurable은 코퍼스가 사전보다 앞서간 어휘(예: pointelle) — 선행신호 후보이며
    CoverageMetrics(concept_match 축)에 집계된다. 사전 확장은 별도 작업.
    """
    facets = concept_facets(concept)
    if not (facets["item"] or facets["materials"] or facets["silhouettes"]
            or facets["color_family"]):
        return {"supply_count": None, "facets": facets, "unmeasurable": True}
    count = 0
    for p in products:
        if facets["item"] and p.item != facets["item"]:
            continue
        if facets["materials"] and not all(m in p.materials for m in facets["materials"]):
            continue
        if facets["silhouettes"] and not all(s in p.silhouettes for s in facets["silhouettes"]):
            continue
        if facets["color_family"] and facets["color_family"] not in p.colors_family:
            continue
        count += 1
    return {"supply_count": count, "facets": facets, "unmeasurable": False}
```

- [ ] **Step 4: 테스트 통과 + 전체 스위트 확인**

Run: `.venv/bin/pytest tests/poc/test_measure.py -q && .venv/bin/pytest -q`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add poc/measure.py tests/poc/test_measure.py
git commit -m "feat(poc): concept↔공급 결정론 매칭 — facet AND·어휘갭 정직표기 (V2 §13.3, SPEC_V3 §7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Pinterest 카테고리 단독 fetch

**Files:**
- Modify: `poc/pinterest.py`
- Test: `tests/poc/test_pinterest.py`

**Interfaces:**
- Consumes: 기존 `_get`, `normalize_category`, `config.PINTEREST_*`.
- Produces: `fetch_categories(client: httpx.Client | None = None) -> dict` — `{"raw", "signals", "failures"}` 계약, 카테고리 details 1콜만. `fetch_all`은 무변경(report v2가 계속 사용).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_pinterest.py` 끝에 추가 (기존 파일의 카테고리 fixture/핸들러 패턴 재사용 — 파일을 먼저 읽고 기존 핸들러 헬퍼가 있으면 그것을 사용):

```python
def test_fetch_categories_only_calls_category_endpoint(monkeypatch):
    monkeypatch.setenv("PINTEREST_ACCESS_TOKEN", "tok")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.path == "/v5/trends/product_categories/details"
        return httpx.Response(200, json=[{
            "product_category": "SWEATERS_AND_CARDIGANS",
            "time_series": {"2026-06-01": 80}, "has_prediction": False,
        }])

    from poc.pinterest import fetch_categories
    client = httpx.Client(transport=httpx.MockTransport(handler),
                          base_url=config.PINTEREST_BASE_URL)
    with client:
        res = fetch_categories(client=client)
    assert calls == ["/v5/trends/product_categories/details"]   # trends/kw_metrics 미호출
    assert len(res["signals"]) == 1
    assert res["signals"][0]["source"] == "pinterest_category"
    assert res["failures"] == []


def test_fetch_categories_without_token(monkeypatch):
    monkeypatch.delenv("PINTEREST_ACCESS_TOKEN", raising=False)
    from poc.pinterest import fetch_categories
    res = fetch_categories()
    assert res["signals"] == [] and len(res["failures"]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_pinterest.py -v`
Expected: 신규 2개 FAIL (`ImportError`), 기존 PASS.

- [ ] **Step 3: 구현**

`poc/pinterest.py`의 `fetch_all` 아래에 추가:

```python
def fetch_categories(client: httpx.Client | None = None) -> dict:
    """카테고리 details 단독 fetch (SPEC_V3 §7 — keywords/metrics는 코퍼스·검증 용도 제외).

    M2 weekly 측정용. fetch_all(3축)은 report v2 경로에서 그대로 유지.
    """
    token = os.environ.get("PINTEREST_ACCESS_TOKEN")
    if not token:
        return {"raw": {}, "signals": [], "failures": [
            {"call": "pinterest_category", "error": "PINTEREST_ACCESS_TOKEN 환경변수 없음"}]}

    result = {"raw": {}, "signals": [], "failures": []}
    own = client is None
    if own:
        client = httpx.Client(base_url=config.PINTEREST_BASE_URL, timeout=20)
    client.headers["Authorization"] = f"Bearer {token}"
    try:
        _get(client, "/v5/trends/product_categories/details",
             {"region": config.PINTEREST_REGION,
              "product_categories": ",".join(config.PINTEREST_CATEGORIES)},
             "pinterest_category", result, normalize_category)
    finally:
        if own:
            client.close()
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_pinterest.py -q`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add poc/pinterest.py tests/poc/test_pinterest.py
git commit -m "feat(poc): pinterest 카테고리 단독 fetch — M2 측정은 category만 (SPEC_V3 §7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 머지 번들 스키마 + 조립 (`poc/bundle.py`)

**Files:**
- Create: `poc/bundle.py`
- Create: `tests/poc/test_bundle.py`

**Interfaces:**
- Consumes: `measure.series_delta / match_supply`, `datalayer.aggregate.brand_aggregate`, `datalayer.records.BrandExtractionResult`.
- Produces (M3 LLM#2의 입력 계약이자 M4 저장의 원천 — 이 스키마가 v3 파이프라인의 중심 계약):
  - pydantic 모델 `NaverMeasure`, `SupplyMeasure`, `ConceptMeasurement`, `AxisCoverage`, `MergeBundle` (`schema_version="3.0"`).
  - `iso_week(now: datetime) -> str` — Asia/Seoul 기준 `"2026-W30"` 형식 (V2 §13.6 business date 규칙).
  - `editorial_count(concept: dict) -> int` — `source_refs` 중 기사 ref(`a` 접두)만 count.
  - `assemble(concepts, naver_result, pinterest_result, extraction_results, *, now, supply_error=None) -> MergeBundle`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_bundle.py` 생성:

```python
"""머지 번들 스키마+조립 테스트 (SPEC_V3 §7). LLM·네트워크 없음."""
from datetime import datetime, timezone

from datalayer.records import BrandExtractionResult, ProductRecord
from poc.bundle import MergeBundle, assemble, editorial_count, iso_week

NOW = datetime(2026, 7, 23, 3, 0, tzinfo=timezone.utc)


def _rec(**kw) -> ProductRecord:
    base = dict(brand="b", url="https://x/p", item=None, colors_raw=[],
                price_native=None, currency=None, compare_at_native=None,
                on_sale=False, materials=[], published_at=None, source="t")
    base.update(kw)
    return ProductRecord(**base)


def _concept(**kw) -> dict:
    base = dict(label_ko="캐시미어 니트", label_en="cashmere knit", aliases=[],
                category="소재", naver_queries=["캐시미어 니트"],
                source_refs=["a0000000001", "w0", "a0000000002"], rationale="r")
    base.update(kw)
    return base


def _naver_result(label: str) -> dict:
    series = [{"period": f"2026-06-{i+1:02d}", "ratio": r}
              for i, r in enumerate([10, 10, 10, 10, 20, 20, 20, 20])]
    return {"raw": {"concept_trend_b0": {}},
            "signals": [{"source": "concept_trend", "group": label, "series": series,
                         "requested_segment": "25-39", "observed_segment": "25-39",
                         "coverage_mismatch": False, "note": "n"}],
            "failures": []}


_EMPTY = {"raw": {}, "signals": [], "failures": []}


def test_iso_week_uses_seoul_business_date():
    assert iso_week(NOW) == "2026-W30"


def test_editorial_count_counts_article_refs_only():
    # §6.2 ref 문법: 기사 a<sha10> / 웹서치 w{i}
    assert editorial_count(_concept()) == 2


def test_assemble_joins_axes_per_concept():
    concepts = [_concept(),
                _concept(label_ko="포인텔 니트", label_en="pointelle knit",
                         source_refs=["a0000000001"])]
    extraction = [
        BrandExtractionResult(brand="A", source="shopify",
                              products=[_rec(item="Sweater", materials=["cashmere"])]),
        BrandExtractionResult(brand="B", source=None, products=[], failure="죽음"),
    ]
    b = assemble(concepts, _naver_result("캐시미어 니트"), _EMPTY, extraction, now=NOW)
    assert isinstance(b, MergeBundle) and b.schema_version == "3.0"
    assert b.iso_week == "2026-W30"

    cash = b.concepts[0]
    assert cash.naver is not None
    assert cash.naver.direction == "up" and cash.naver.delta_pct == 100.0
    assert cash.supply.supply_count == 1
    assert cash.editorial_count == 2

    point = b.concepts[1]
    assert point.naver is None                      # 시그널 없음 = None (0과 구분)
    assert point.supply.unmeasurable is True        # 어휘 갭 정직 표기


def test_assemble_coverage_is_honest():
    concepts = [_concept()]
    extraction = [
        BrandExtractionResult(brand="A", source="shopify", products=[_rec()]),
        BrandExtractionResult(brand="B", source=None, products=[], failure="죽음"),
    ]
    b = assemble(concepts, _naver_result("캐시미어 니트"), _EMPTY, extraction, now=NOW)
    assert b.coverage["naver"].attempted == 1 and b.coverage["naver"].succeeded == 1
    assert b.coverage["supply"].attempted == 2 and b.coverage["supply"].succeeded == 1
    assert b.coverage["supply"].ratio == 0.5
    assert b.coverage["concept_match"].attempted == 1


def test_assemble_axis_death_still_builds_bundle():
    # M2 수용 기준: 축 실패 시에도 번들 생성 + CoverageMetrics 기록
    fail = {"raw": {}, "signals": [],
            "failures": [{"call": "concept_trend", "error": "환경변수 없음"}]}
    b = assemble([_concept()], fail, _EMPTY, [], now=NOW, supply_error="VPN 죽음")
    assert b.concepts[0].naver is None
    assert b.coverage["naver"].failures                       # 실패 사유 보존
    assert b.coverage["supply"].attempted == 0
    assert b.coverage["supply"].ratio is None                 # 분모 0 → None, 0% 아님(V2 §8.7)
    assert b.coverage["supply"].failures[0]["error"] == "VPN 죽음"


def test_bundle_round_trips_json():
    b = assemble([_concept()], _EMPTY, _EMPTY, [], now=NOW)
    restored = MergeBundle.model_validate_json(b.model_dump_json())
    assert restored.iso_week == b.iso_week
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_bundle.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'poc.bundle'`).

- [ ] **Step 3: 구현**

`poc/bundle.py` 생성:

```python
"""머지 번들 (SPEC_V3 §7) — concepts + 축별 측정치 + CoverageMetrics 단일 JSON.

M3 LLM#2의 입력 계약이자 M4 concept_weekly 저장의 원천. 조립은 순수 함수 — I/O 없음.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from datalayer.aggregate import brand_aggregate
from datalayer.records import BrandExtractionResult
from poc.measure import match_supply, series_delta

SCHEMA_VERSION = "3.0"


class NaverMeasure(BaseModel):
    series: list[dict]
    delta_pct: float | None
    direction: str
    recent_mean: float | None
    prior_mean: float | None


class SupplyMeasure(BaseModel):
    supply_count: int | None      # None = 어휘 갭(측정 불가), 0 = 측정됐는데 공급 없음(갭 신호)
    facets: dict
    unmeasurable: bool


class ConceptMeasurement(BaseModel):
    concept: dict
    naver: NaverMeasure | None    # None = 축 실패/시그널 부재 (0과 구분)
    supply: SupplyMeasure | None
    editorial_count: int


class AxisCoverage(BaseModel):
    attempted: int
    succeeded: int
    ratio: float | None           # 분모 0 → None (V2 §8.7 — 0%로 표현 금지)
    failures: list[dict] = Field(default_factory=list)


class MergeBundle(BaseModel):
    schema_version: str = SCHEMA_VERSION
    iso_week: str
    generated_at: str
    concepts: list[ConceptMeasurement]
    pinterest_category: list[dict]
    supply_brands: list[dict]     # brand_aggregate 블록 (LLM#2 근거·M5 report 재사용)
    coverage: dict[str, AxisCoverage]


def iso_week(now: datetime) -> str:
    """Asia/Seoul 기준 business date의 ISO 주 (V2 §13.6)."""
    y, w, _ = now.astimezone(ZoneInfo("Asia/Seoul")).isocalendar()
    return f"{y}-W{w:02d}"


def editorial_count(concept: dict) -> int:
    """§6.2 ref 문법 — 기사 ref(a<sha10>)만 count, 웹서치(w{i}) 제외."""
    return sum(1 for r in concept.get("source_refs", []) if r.startswith("a"))


def _axis(attempted: int, succeeded: int, failures: list[dict]) -> AxisCoverage:
    ratio = round(succeeded / attempted, 2) if attempted else None
    return AxisCoverage(attempted=attempted, succeeded=succeeded,
                        ratio=ratio, failures=failures)


def assemble(concepts: list[dict],
             naver_result: dict,
             pinterest_result: dict,
             extraction_results: list[BrandExtractionResult],
             *, now: datetime,
             supply_error: str | None = None) -> MergeBundle:
    products = [p for r in extraction_results for p in r.products]
    by_group = {s["group"]: s for s in naver_result["signals"]}

    measured: list[ConceptMeasurement] = []
    for c in concepts:
        sig = by_group.get(c["label_ko"])
        naver = NaverMeasure(series=sig["series"], **series_delta(sig["series"])) if sig else None
        supply = SupplyMeasure(**match_supply(c, products)) if extraction_results else None
        measured.append(ConceptMeasurement(
            concept=c, naver=naver, supply=supply, editorial_count=editorial_count(c)))

    naver_batches = -(-len(concepts) // 5) if concepts else 0   # ceil
    supply_failures = [{"call": "supply", "error": supply_error}] if supply_error else [
        {"call": r.brand, "error": r.failure} for r in extraction_results if r.failure]
    coverage = {
        "naver": _axis(naver_batches, len(naver_result["raw"]), naver_result["failures"]),
        "pinterest": _axis(1, len(pinterest_result["raw"]), pinterest_result["failures"]),
        "supply": _axis(len(extraction_results),
                        sum(1 for r in extraction_results if r.products), supply_failures),
        "concept_match": _axis(
            len(concepts),
            sum(1 for m in measured if m.supply and not m.supply.unmeasurable),
            []),
    }
    return MergeBundle(
        iso_week=iso_week(now),
        generated_at=now.isoformat(),
        concepts=measured,
        pinterest_category=pinterest_result["signals"],
        supply_brands=[brand_aggregate(r) for r in extraction_results],
        coverage=coverage,
    )
```

- [ ] **Step 4: 테스트 통과 + 전체 스위트 확인**

Run: `.venv/bin/pytest tests/poc/test_bundle.py -q && .venv/bin/pytest -q`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add poc/bundle.py tests/poc/test_bundle.py
git commit -m "feat(poc): 머지 번들 스키마+조립 — concepts+3축+CoverageMetrics 단일 JSON (SPEC_V3 §7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: weekly CLI 오케스트레이션 (`poc/weekly.py`)

**Files:**
- Create: `poc/weekly.py`
- Modify: `ops/cron.md` (weekly 명령 교체)
- Create: `tests/poc/test_weekly.py`

**Interfaces:**
- Consumes: `corpus.main(now)`, `naver.fetch_concept_trends`, `pinterest.fetch_categories`, `datalayer.extract.extract_all`, `bundle.assemble`.
- Produces: `weekly.run(now: datetime | None = None) -> dict` — 요약 dict 반환, 부수효과로 `out/merge_bundle.json`(최신) + `out/weekly/merge_bundle_{iso_week}.json`(아카이브) 기록. CLI `python -m poc.weekly`. M3가 이 파일을 읽는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_weekly.py` 생성:

```python
"""weekly 오케스트레이션 테스트 — 축 실패 격리가 M2 수용 기준 (SPEC_V3 §12). LLM·네트워크 없음."""
import json
from datetime import datetime, timezone

from poc import config, weekly

NOW = datetime(2026, 7, 23, 3, 0, tzinfo=timezone.utc)

_CONCEPT = {"label_ko": "캐시미어 니트", "label_en": "cashmere knit", "aliases": [],
            "category": "소재", "naver_queries": ["캐시미어 니트"],
            "source_refs": ["a0000000001"], "rationale": "r"}


def _setup(monkeypatch, tmp_path, *, naver_raises: bool):
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    (tmp_path / "concepts.json").write_text(json.dumps([_CONCEPT], ensure_ascii=False))
    monkeypatch.setattr(weekly.corpus, "main",
                        lambda now=None: {"concepts": 1, "dropped": 0})

    def fake_naver(concepts):
        if naver_raises:
            raise RuntimeError("boom")
        return {"raw": {}, "signals": [], "failures": []}

    monkeypatch.setattr(weekly.naver, "fetch_concept_trends", fake_naver)
    monkeypatch.setattr(weekly.pinterest, "fetch_categories",
                        lambda: {"raw": {}, "signals": [], "failures": []})
    monkeypatch.setattr(weekly, "extract_all", lambda brands: [])


def test_weekly_writes_bundle_and_archive(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, naver_raises=False)
    summary = weekly.run(now=NOW)
    assert summary["iso_week"] == "2026-W30" and summary["concepts"] == 1
    latest = json.loads((tmp_path / "merge_bundle.json").read_text())
    archive = json.loads((tmp_path / "weekly" / "merge_bundle_2026-W30.json").read_text())
    assert latest["schema_version"] == "3.0"
    assert latest == archive


def test_weekly_axis_exception_is_isolated(monkeypatch, tmp_path):
    # M2 수용 기준: 축 1개가 raise해도 번들은 생성되고 실패가 coverage에 남는다
    _setup(monkeypatch, tmp_path, naver_raises=True)
    weekly.run(now=NOW)
    bundle = json.loads((tmp_path / "merge_bundle.json").read_text())
    assert bundle["concepts"][0]["naver"] is None
    assert any("boom" in f["error"]
               for f in bundle["coverage"]["naver"]["failures"])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_weekly.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'poc.weekly'`).

- [ ] **Step 3: 구현**

`poc/weekly.py` 생성:

```python
"""weekly 분석 run (SPEC_V3 §5.2) — LLM#1 코퍼스 → 결정론 측정 3축 → 머지 번들.

축 실패는 격리(§4): 어떤 축이 죽어도 번들은 산출되고 CoverageMetrics에 남는다.
M3에서 LLM#2 합성이 이 뒤에 붙는다. python -m poc.weekly (cron: ops/cron.md).
"""
import json
from datetime import datetime, timezone

from datalayer.extract import extract_all
from poc import bundle, config, corpus, naver, pinterest


def _fail_result(call: str, exc: Exception) -> dict:
    return {"raw": {}, "signals": [],
            "failures": [{"call": call, "error": f"{type(exc).__name__}: {exc}"}]}


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    config.OUT_DIR.mkdir(exist_ok=True)

    corpus_status = corpus.main(now=now)
    concepts_path = config.OUT_DIR / "concepts.json"
    concepts = json.loads(concepts_path.read_text()) if concepts_path.exists() else []

    try:
        naver_result = naver.fetch_concept_trends(concepts)
    except Exception as e:
        naver_result = _fail_result("concept_trend", e)
    try:
        pinterest_result = pinterest.fetch_categories()
    except Exception as e:
        pinterest_result = _fail_result("pinterest_category", e)
    supply_error = None
    try:
        extraction = extract_all(config.BRANDS)
    except Exception as e:
        extraction, supply_error = [], f"{type(e).__name__}: {e}"

    merged = bundle.assemble(concepts, naver_result, pinterest_result, extraction,
                             now=now, supply_error=supply_error)
    payload = merged.model_dump_json(indent=2)
    (config.OUT_DIR / "merge_bundle.json").write_text(payload, encoding="utf-8")
    weekly_dir = config.OUT_DIR / "weekly"
    weekly_dir.mkdir(exist_ok=True)
    (weekly_dir / f"merge_bundle_{merged.iso_week}.json").write_text(payload, encoding="utf-8")

    return {
        "corpus": corpus_status,
        "iso_week": merged.iso_week,
        "concepts": len(merged.concepts),
        "coverage": {k: v.ratio for k, v in merged.coverage.items()},
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
```

(예기치 못한 예외는 그대로 traceback + 비0 exit — cron이 잡는다. 번들 산출 성공이면 exit 0, 부분 실패 포함.)

`ops/cron.md`의 weekly 절 교체:

```markdown
## weekly — 분석 run (코퍼스 → 측정 3축 → 머지 번들)

    0 10 * * 1 cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.weekly >> out/weekly_run.log 2>&1

- weekly 요일은 config 취급(SPEC_V3 §5.2) — 현재 월요일 10:00 KST.
- LLM·API 예산은 weekly run에만 발생(V2 §21). M2 기준 LLM 호출은 corpus(LLM#1) 1회뿐.
- M3(LLM#2 합성)가 이 run 뒤에 붙는다.
```

- [ ] **Step 4: 테스트 통과 + 전체 스위트 확인**

Run: `.venv/bin/pytest tests/poc/test_weekly.py -q && .venv/bin/pytest -q`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add poc/weekly.py tests/poc/test_weekly.py ops/cron.md
git commit -m "feat(poc): weekly CLI — 코퍼스→3축 격리 측정→머지 번들 (SPEC_V3 §5.2, §7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: 라이브 스모크 — M2 수용 기준 검증

**Files:**
- 코드 변경 없음 (실패 발견 시 해당 태스크로 돌아가 수정)

M2 수용 기준(SPEC_V3 §12): ① 번들 스키마 검증 통과 ② 축 1개 실패 시에도 번들 생성 + CoverageMetrics 기록. ②는 Task 8 테스트로 이미 증명 — 라이브는 ①과 실데이터 품질 확인.

- [ ] **Step 1: 사전 조건 확인**

- `.env`에 `NCP_API_HUB_CLIENT_ID/SECRET`, `PINTEREST_ACCESS_TOKEN`, `ANTHROPIC_API_KEY` 존재.
- Shopify 9몰은 IP 차단 이력 있음 — VPN 켜고 실행(메모리: VPN+백오프로 해결 이력). VPN 불가 시에도 실행은 진행 — supply 축 실패가 CoverageMetrics에 기록되는 것 자체가 정상 동작.

- [ ] **Step 2: 라이브 실행**

Run: `.venv/bin/python -m poc.rss && .venv/bin/python -m poc.weekly`
Expected: rss exit 0, weekly가 요약 JSON 출력 (`iso_week`, `concepts` ≥ 1, `coverage` 축별 ratio).

- [ ] **Step 3: 산출물 검증**

```bash
.venv/bin/python - <<'EOF'
import json
from poc.bundle import MergeBundle
b = MergeBundle.model_validate_json(open("out/merge_bundle.json").read())   # ① 스키마 검증
naver_ok = sum(1 for c in b.concepts if c.naver)
measurable = sum(1 for c in b.concepts if c.supply and not c.supply.unmeasurable)
print(f"week={b.iso_week} concepts={len(b.concepts)} naver측정={naver_ok} "
      f"공급측정가능={measurable} 공급브랜드={sum(1 for s in b.supply_brands if s.get('count'))}")
for k, v in b.coverage.items():
    print(f"  {k}: {v.succeeded}/{v.attempted} ratio={v.ratio} failures={len(v.failures)}")
EOF
```

Expected: 검증 예외 없음, `naver측정 ≥ 1`(concepts에 한국어 쿼리가 있으므로 시계열이 잡혀야 정상), quince count가 종전 대비 크게 증가(유니온 효과, ~107 근처), unmeasurable concept이 있으면 concept_match ratio < 1.0으로 정직 표기.

- [ ] **Step 4: 결과 기록**

라이브 수치(축별 coverage, quince count, unmeasurable 목록)를 오너에게 보고. 이상 발견 시 해당 태스크로 복귀. 이상 없으면 M2 완료 — 오너 승인 후 merge/푸시 결정.

---

## Self-Review

- **Spec coverage:** SPEC_V3 §12 M2 4요소 — concepts→NAVER(Task 3+4+7), Pinterest 카테고리(Task 6+7), 공급 배선+매칭(Task 5+7, extract_all 재사용), merge 번들+CoverageMetrics(Task 7+8). 페이지네이션 fix: quince(Task 2, 실측 기반 유니온), kolonmall(정책 한계 확정 — 우회 없음, 문서화). M1 이관분(Task 1): exit code·`is None`·ref 주석 포함, websearch 안정 id는 M4로 명시 이관(§6.2 docstring에 기록).
- **수용 기준:** ① 번들 스키마 검증 = Task 7 pydantic + Task 9 라이브 재검증. ② 축 실패 격리 = Task 7 `test_assemble_axis_death` + Task 8 `test_weekly_axis_exception_is_isolated`.
- **Type consistency:** `{"raw","signals","failures"}` 축 계약 3곳 동일(naver/pinterest/실패 placeholder). `series_delta` 반환 키 = `NaverMeasure` 필드. `match_supply` 반환 키 = `SupplyMeasure` 필드. ref 접두(`a`/`w`) Task 1 주석 = Task 7 `editorial_count` 구현 일치.
- **잔여 리스크(플랜 범위 밖, 기록만):** quince 카드가 productId 중복(색상 그룹 카드)일 때 첫 카드만 채택하는 기존 dedup은 후속 카드의 색상 variant를 버린다 — 기존 동작, M2 무관, 필요 시 별도 이슈. NAVER groupName에 label_ko 중복 concept이 오면 조인이 마지막 시그널을 채택 — validator가 라벨 중복을 막지 않으나 실측 16 concepts에서 미발생, M3 validator 확장 후보.
