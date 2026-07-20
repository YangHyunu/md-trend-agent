# PoC (크롤링+트렌드) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m poc.run` 한 번으로 NAVER 트렌드 신호 + 브랜드 공식몰/웹 크롤링 데이터를 수집하고, 근거 ID가 연결된 MD 상품기획 보고서(report.md)를 생성한다.

**Architecture:** 순차 실행 CLI 파이프라인. `config → naver → collect → analyze(LLM 2패스) → report` 5개 모듈이 각각 독립 실행 가능하며 중간 산출물을 `out/`에 JSON으로 덤프한다. 오케스트레이터(Hermes), DB, 서버 없음.

**Tech Stack:** Python 3.11+, httpx (NAVER API HUB), tavily-python (웹 검색), crawl4ai (크롤링), anthropic SDK + `messages.parse()` (구조화 LLM 출력), pydantic.

## Global Constraints

전 태스크 공통 — POC_SPEC.md에서 온 하드 제약. 모든 코드가 지켜야 함.

- NAVER API HUB만 사용: base URL `https://naverapihub.apigw.ntruss.com`, 헤더 `X-NCP-APIGW-API-KEY-ID` / `X-NCP-APIGW-API-KEY`. 구 `openapi.naver.com` 금지.
- 연령 코드: Search Trend 25~39세 = `["4","5","6"]` / Shopping Insight 20~39세 = `["20","30"]`. 혼용 금지.
- Shopping Insight 결과에는 `requested_segment: "25-39"`, `observed_segment: "20-39"`, `coverage_mismatch: true`를 반드시 저장하고 보고서에 표시.
- `ratio`는 요청 내 상대값(최대=100) — 서로 다른 요청 간 절대 비교 금지, 보고서에 주의문 필수.
- 예산 상수: Tavily 질의 ≤8, 수집 URL ≤20, NAVER 호출 ≤6, Crawl4AI timeout 60초/URL, LLM 호출 패스당 1회+재시도 1회. 초과 시 자르고 진행, 예외로 죽지 않음.
- 공개 `http/https` URL만. Instagram(PLUSH'MERE)은 `auto_collect=False`, 수집 안 함.
- 원문 전체 재배포 금지 — 발췌(excerpt)와 출처 링크만 저장.
- LLM 모델: `claude-opus-4-8`, `thinking={"type": "adaptive"}`. temperature/top_p 파라미터 금지(400 에러). 마지막 assistant prefill 금지(400 에러). 구조화 출력은 `client.messages.parse(..., output_format=PydanticModel)` 사용.
- 시크릿은 프로젝트 루트 `.env`에서 로드 (`NCP_API_HUB_CLIENT_ID`, `NCP_API_HUB_CLIENT_SECRET`, `TAVILY_API_KEY`, `ANTHROPIC_API_KEY` 이미 존재). 값을 로그/보고서에 출력하지 않는다.
- 테스트 스위트 없음(POC_SPEC §3 제외 항목). 각 모듈의 `python -m poc.<모듈> --offline` 셀프체크(assert)와 live 스모크 실행이 검증 수단.

## File Structure

```text
poc/
  __init__.py    # 빈 파일
  config.py      # 브랜드 세트, 키워드, 분석 조건, 예산 상수, .env 로드
  naver.py       # API HUB 클라이언트: payload 빌더(순수함수) + 호출 + 정규화
  collect.py     # Tavily 검색 + Crawl4AI 수집 + evidence 생성
  analyze.py     # LLM 2패스 (리서처 → MD분석가), pydantic 스키마
  report.py      # Markdown 렌더 (순수함수, LLM 자유생성 금지)
  run.py         # 순차 실행 entry point, out/ 덤프
requirements.txt
out/             # 산출물 (gitignore)
```

---

### Task 1: 스캐폴드 + config.py

**Files:**
- Create: `requirements.txt`
- Create: `poc/__init__.py`
- Create: `poc/config.py`
- Modify: `.gitignore` (`out/` 추가)

**Interfaces:**
- Produces: `config.BRANDS: list[Brand]` (Brand: name/url/channel/purpose/auto_collect), `config.SEARCH_KEYWORD_GROUPS`, `config.SHOPPING_KEYWORDS`, `config.SHOPPING_CAT_ID`, `config.SEARCH_TREND_AGES`, `config.SHOPPING_AGES`, `config.TAVILY_QUERIES`, `config.ANALYSIS: dict`, `config.period() -> tuple[str, str]`, 예산 상수들(`MAX_TAVILY_QUERIES`, `MAX_CRAWL_URLS`, `MAX_NAVER_CALLS`, `CRAWL_TIMEOUT_SEC`, `MAX_PER_DOMAIN`), `config.NAVER_BASE_URL`, `config.OUT_DIR: Path`

- [ ] **Step 1: requirements.txt 작성**

```text
httpx>=0.27
pydantic>=2.7
anthropic>=0.40
tavily-python>=0.5
crawl4ai>=0.6
python-dotenv>=1.0
```

- [ ] **Step 2: 가상환경 생성 및 설치**

Run:
```bash
cd /Users/yanghyeon-u/Desktop/Claude-BZRR-SUB
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/crawl4ai-setup
```
Expected: 설치 성공. `crawl4ai-setup`이 playwright chromium을 내려받음 (수 분 걸릴 수 있음). 실패 시 `.venv/bin/python -m playwright install chromium`로 재시도.

- [ ] **Step 3: `.gitignore`에 `out/` 추가**

기존 `.gitignore` 끝에 한 줄:
```text
out/
```

- [ ] **Step 4: `poc/__init__.py` (빈 파일) + `poc/config.py` 작성**

```python
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / "out"

NAVER_BASE_URL = "https://naverapihub.apigw.ntruss.com"


@dataclass(frozen=True)
class Brand:
    name: str
    url: str
    channel: str
    purpose: str
    auto_collect: bool = True


# SPEC.md §10 cashmere-reference seed data 그대로. 값 임의 변경 금지.
BRANDS: list[Brand] = [
    Brand("guestinresidence", "https://guestinresidence.com/", "공식몰", "Young & Trendy 캐시미어 디자인"),
    Brand("Extreme cashmere", "https://extreme-cashmere.com/", "공식몰", "컬러 조합"),
    Brand("&Daughter", "https://www.and-daughter.com/", "공식몰", "룩북, 브랜드 컨셉, 브루클린 감성"),
    Brand("Lisa Yang", "https://us.lisa-yang.com/", "공식몰", "아시아 고객 선호 가능 디자인"),
    Brand("Arch4", "https://www.arch4.co.uk/", "공식몰", "베이직과 차별화된 디테일"),
    Brand("Le Cashmere", "https://www.kolonmall.com/Brands/LECASHMERE", "유통몰", "룩북 컬러 조합"),
    Brand("Iris Von Arnim", "https://irisvonarnim.com/us/", "공식몰", "Brushed Cashmere 라인"),
    Brand("LE17 SEPTEMBRE", "https://en.le17septembre.com/", "공식몰", "베이직과 차별화된 디테일"),
    Brand("Quince", "https://www.quince.com/women/cashmere", "공식몰", "소재와 기본 아이템 구성"),
    Brand("cashmereinlove", "https://www.cashmereinlove.com/", "공식몰", "브라렛, 레깅스 등 독특한 아이템"),
    Brand("COS", "https://www.cos.com/en-us/women/knitwear", "공식몰", "다양한 니트웨어 아이디어"),
    Brand("PLUSH'MERE", "https://www.instagram.com/plushmere/?hl=en", "Instagram", "Colorblock 스타일", auto_collect=False),
]

# --- NAVER 연령 코드 (SPEC.md DataLab Client 절. 두 API 코드 체계 혼용 금지) ---
SEARCH_TREND_AGES = ["4", "5", "6"]   # Search Trend 25~39세
SHOPPING_AGES = ["20", "30"]          # Shopping Insight 20~39세 (25~39 정확 표현 불가)

# Search Trend: 최대 5개 그룹, 그룹당 최대 20개 검색어
SEARCH_KEYWORD_GROUPS = [
    {"groupName": "캐시미어", "keywords": ["캐시미어", "캐시미어니트", "캐시미어스웨터"]},
    {"groupName": "니트웨어", "keywords": ["니트", "스웨터", "가디건"]},
    {"groupName": "프리미엄소재", "keywords": ["홀가먼트", "램스울", "메리노울"]},
]

# Shopping Insight 키워드별: 최대 5개 그룹, 그룹당 검색어 1개
SHOPPING_KEYWORDS = ["캐시미어니트", "캐시미어가디건", "캐시미어스웨터", "여성니트", "캐시미어코트"]

# 네이버쇼핑 cat_id: 패션의류 > 여성의류 > 니트/스웨터 로 추정.
# 첫 live 실행 전 검증: search.shopping.naver.com 에서 해당 카테고리 페이지 URL의 catId 확인.
# 틀리면 NAVER가 400/빈 결과 반환 → naver.py가 failures에 기록하고 계속 진행함.
SHOPPING_CAT_ID = "50000804"
SHOPPING_CAT_NAME = "여성 니트/스웨터"

TAVILY_QUERIES = [
    "cashmere knitwear trends 2026 women",
    "여성 캐시미어 니트 트렌드 2026",
    "cashmere sweater color trends fall winter 2026",
    "캐시미어 브랜드 니트 신상",
    "extreme cashmere new collection",
    "quince cashmere women sweater review",
    "홀가먼트 캐시미어 니트",
    "cashmere knitwear silhouette trend",
]

# 분석 조건 (POC_SPEC §5 고정)
ANALYSIS = {
    "category": "여성 니트웨어 (캐시미어 중심)",
    "target": "한국 여성 25~39세",
    "price_range": "20만~70만원",
    "period_weeks": 8,
    "focus": "경쟁 아이템, 컬러 조합, 주요 소재, 독특한 캐시미어 아이템",
}


def period() -> tuple[str, str]:
    """최근 8주. (start, end) ISO date 문자열."""
    end = date.today()
    start = end - timedelta(weeks=ANALYSIS["period_weeks"])
    return start.isoformat(), end.isoformat()


# --- 예산 (POC_SPEC §7. 초과 시 자르고 진행) ---
MAX_TAVILY_QUERIES = 8
MAX_CRAWL_URLS = 20
MAX_NAVER_CALLS = 6
CRAWL_TIMEOUT_SEC = 60
MAX_PER_DOMAIN = 5
```

- [ ] **Step 5: import 검증**

Run: `.venv/bin/python -c "from poc import config; assert len(config.BRANDS) == 12; assert sum(b.auto_collect for b in config.BRANDS) == 11; s,e = config.period(); print(s, e, 'OK')"`
Expected: `2026-05-25 2026-07-20 OK` (날짜는 실행일 기준)

- [ ] **Step 6: Commit**

```bash
git add .gitignore CLAUDE.md SPEC.md POC_SPEC.md docs/ ops/ requirements.txt poc/
git commit -m "feat: PoC 스캐폴드 + config (브랜드 세트, 키워드, 예산)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: naver.py — API HUB 클라이언트

**Files:**
- Create: `poc/naver.py`

**Interfaces:**
- Consumes: `config.SEARCH_KEYWORD_GROUPS`, `config.SHOPPING_*`, `config.period()`, `config.NAVER_BASE_URL`, env `NCP_API_HUB_CLIENT_ID`/`NCP_API_HUB_CLIENT_SECRET`
- Produces:
  - `build_search_trend_payload(start: str, end: str) -> dict`
  - `build_shopping_category_payload(start: str, end: str) -> dict`
  - `build_shopping_keyword_payload(start: str, end: str) -> dict`
  - `fetch_all() -> dict` — `{"raw": {엔드포인트별 원응답}, "signals": [정규화 신호], "failures": [{"call": str, "error": str}]}`
  - signal 형식: `{"source": "search_trend"|"shopping_category"|"shopping_keyword", "group": str, "series": [{"period": str, "ratio": float}], "requested_segment": "25-39", "observed_segment": str, "coverage_mismatch": bool, "note": str}`

- [ ] **Step 1: `poc/naver.py` 작성**

```python
"""NAVER API HUB 클라이언트. Search Trend + Shopping Insight."""
import json
import os
import sys

import httpx

from poc import config

RATIO_NOTE = "ratio는 각 요청 결과의 최대값을 100으로 둔 상대값. 서로 다른 요청 간 절대 비교 금지."


def build_search_trend_payload(start: str, end: str) -> dict:
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "keywordGroups": config.SEARCH_KEYWORD_GROUPS,
        "gender": "f",
        "ages": config.SEARCH_TREND_AGES,
    }


def build_shopping_category_payload(start: str, end: str) -> dict:
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "category": [{"name": config.SHOPPING_CAT_NAME, "param": [config.SHOPPING_CAT_ID]}],
        "gender": "f",
        "ages": config.SHOPPING_AGES,
    }


def build_shopping_keyword_payload(start: str, end: str) -> dict:
    return {
        "startDate": start,
        "endDate": end,
        "timeUnit": "week",
        "category": config.SHOPPING_CAT_ID,
        "keyword": [{"name": kw, "param": [kw]} for kw in config.SHOPPING_KEYWORDS],
        "gender": "f",
        "ages": config.SHOPPING_AGES,
    }


def _normalize(raw: dict, source: str, coverage_mismatch: bool) -> list[dict]:
    signals = []
    for r in raw.get("results", []):
        signals.append({
            "source": source,
            "group": r.get("title", ""),
            "series": r.get("data", []),
            "requested_segment": "25-39",
            "observed_segment": "20-39" if coverage_mismatch else "25-39",
            "coverage_mismatch": coverage_mismatch,
            "note": RATIO_NOTE,
        })
    return signals


CALLS = [
    ("search_trend", "/search-trend/v1/search", build_search_trend_payload, False),
    ("shopping_category", "/shopping/v1/categories", build_shopping_category_payload, True),
    ("shopping_keyword", "/shopping/v1/category/keywords", build_shopping_keyword_payload, True),
]


def fetch_all() -> dict:
    headers = {
        "X-NCP-APIGW-API-KEY-ID": os.environ["NCP_API_HUB_CLIENT_ID"],
        "X-NCP-APIGW-API-KEY": os.environ["NCP_API_HUB_CLIENT_SECRET"],
        "Content-Type": "application/json",
    }
    start, end = config.period()
    result = {"raw": {}, "signals": [], "failures": []}
    calls_made = 0
    with httpx.Client(base_url=config.NAVER_BASE_URL, headers=headers, timeout=20) as client:
        for name, path, builder, mismatch in CALLS:
            if calls_made >= config.MAX_NAVER_CALLS:
                result["failures"].append({"call": name, "error": "NAVER 호출 예산 초과로 생략"})
                continue
            calls_made += 1
            try:
                resp = client.post(path, json=builder(start, end))
                resp.raise_for_status()
                raw = resp.json()
                result["raw"][name] = raw
                result["signals"].extend(_normalize(raw, name, mismatch))
            except Exception as e:
                result["failures"].append({"call": name, "error": f"{type(e).__name__}: {e}"})
    return result


def _offline_check() -> None:
    p = build_search_trend_payload("2026-05-25", "2026-07-20")
    assert p["ages"] == ["4", "5", "6"], "Search Trend 연령 코드 오류"
    assert len(p["keywordGroups"]) <= 5
    assert all(len(g["keywords"]) <= 20 for g in p["keywordGroups"])

    c = build_shopping_category_payload("2026-05-25", "2026-07-20")
    assert c["ages"] == ["20", "30"], "Shopping Insight 연령 코드 오류"
    assert len(c["category"]) <= 3

    k = build_shopping_keyword_payload("2026-05-25", "2026-07-20")
    assert len(k["keyword"]) <= 5
    assert all(len(x["param"]) == 1 for x in k["keyword"])

    fixture = {"results": [{"title": "캐시미어니트", "data": [{"period": "2026-06-01", "ratio": 100.0}]}]}
    sig = _normalize(fixture, "shopping_keyword", True)[0]
    assert sig["coverage_mismatch"] is True
    assert sig["observed_segment"] == "20-39"
    assert sig["requested_segment"] == "25-39"
    sig2 = _normalize(fixture, "search_trend", False)[0]
    assert sig2["coverage_mismatch"] is False
    print("naver offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
    else:
        config.OUT_DIR.mkdir(exist_ok=True)
        res = fetch_all()
        (config.OUT_DIR / "naver_raw.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"signals={len(res['signals'])} failures={len(res['failures'])}")
        for f in res["failures"]:
            print(" FAIL", f["call"], f["error"][:200])
```

- [ ] **Step 2: 오프라인 셀프체크**

Run: `.venv/bin/python -m poc.naver --offline`
Expected: `naver offline checks OK`

- [ ] **Step 3: cat_id 검증 후 live 스모크**

먼저 브라우저나 curl로 네이버쇼핑 여성 니트/스웨터 카테고리의 실제 `catId`를 확인하고, 다르면 `config.SHOPPING_CAT_ID` 수정.

Run: `.venv/bin/python -m poc.naver`
Expected: `signals=N failures=M` 출력, `out/naver_raw.json` 생성. `search_trend` 신호가 3개(그룹 수)면 정상. shopping 호출이 실패하면 에러 메시지 확인 — cat_id 오류면 config 수정 후 재실행. **주의: 인증 실패(401/403)면 API HUB 콘솔에서 상품 구독 상태 확인 필요 — 코드 문제 아님.** 전부 실패해도 다음 태스크 진행 가능(파이프라인은 부분 실패 허용).

- [ ] **Step 4: Commit**

```bash
git add poc/naver.py
git commit -m "feat: NAVER API HUB 클라이언트 (Search Trend + Shopping Insight)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: collect.py — 웹 검색 + 크롤링 + evidence

**Files:**
- Create: `poc/collect.py`

**Interfaces:**
- Consumes: `config.BRANDS`, `config.TAVILY_QUERIES`, 예산 상수, env `TAVILY_API_KEY`
- Produces:
  - `discover_urls() -> list[dict]` — `[{"url": str, "found_via": str}]`
  - `crawl_urls(urls: list[str]) -> list[dict]` — `[{"url": str, "ok": bool, "text": str, "error": str|None, "fetched_at": str}]` (async 아님 — 내부에서 asyncio.run)
  - `build_evidence(crawl_results: list[dict]) -> list[dict]` — `[{"id": "E001", "url": str, "excerpt": str, "brand": str|None, "source_type": "official"|"web", "fetched_at": str}]`
  - `collect() -> tuple[list[dict], list[dict]]` — (crawl_results, evidence) 전체 실행

- [ ] **Step 1: `poc/collect.py` 작성**

```python
"""Tavily 웹 검색 + Crawl4AI 수집 + evidence 생성."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from poc import config

EXCERPT_CHARS = 3000   # evidence 발췌 길이 (원문 전체 재배포 금지)
MIN_TEXT_CHARS = 500   # 이하면 추출 실패 판정 (SPEC Content Collector 기준)
STORE_TEXT_CHARS = 20000


def _canonical(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}"


def discover_urls() -> list[dict]:
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    found, seen = [], set()
    for q in config.TAVILY_QUERIES[: config.MAX_TAVILY_QUERIES]:
        try:
            resp = client.search(q, max_results=5)
        except Exception as e:
            print(f" tavily FAIL {q!r}: {e}", file=sys.stderr)
            continue
        for r in resp.get("results", []):
            u = r.get("url", "")
            if not u.startswith(("http://", "https://")):
                continue
            c = _canonical(u)
            if c in seen:
                continue
            seen.add(c)
            found.append({"url": u, "found_via": q})
    return found


def _brand_for(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for b in config.BRANDS:
        if not b.auto_collect:
            continue
        if urlparse(b.url).netloc.lower() in host or host in urlparse(b.url).netloc.lower():
            return b.name
    return None


def select_urls(discovered: list[dict]) -> list[str]:
    """공식몰 우선 + 발견 URL, 총 MAX_CRAWL_URLS, 도메인당 MAX_PER_DOMAIN."""
    urls: list[str] = [b.url for b in config.BRANDS if b.auto_collect]
    per_domain: dict[str, int] = {}
    for u in urls:
        d = urlparse(u).netloc.lower()
        per_domain[d] = per_domain.get(d, 0) + 1
    for item in discovered:
        if len(urls) >= config.MAX_CRAWL_URLS:
            break
        u = item["url"]
        d = urlparse(u).netloc.lower()
        if per_domain.get(d, 0) >= config.MAX_PER_DOMAIN:
            continue
        if _canonical(u) in {_canonical(x) for x in urls}:
            continue
        urls.append(u)
        per_domain[d] = per_domain.get(d, 0) + 1
    return urls[: config.MAX_CRAWL_URLS]


async def _crawl_async(urls: list[str]) -> list[dict]:
    from crawl4ai import AsyncWebCrawler
    results = []
    async with AsyncWebCrawler() as crawler:
        for u in urls:
            fetched_at = datetime.now(timezone.utc).isoformat()
            try:
                r = await asyncio.wait_for(
                    crawler.arun(url=u), timeout=config.CRAWL_TIMEOUT_SEC)
                text = str(r.markdown or "") if r.success else ""
                ok = len(text) >= MIN_TEXT_CHARS
                results.append({
                    "url": u, "ok": ok, "text": text[:STORE_TEXT_CHARS],
                    "error": None if ok else f"추출 실패: 본문 {len(text)}자 (<{MIN_TEXT_CHARS})",
                    "fetched_at": fetched_at,
                })
            except Exception as e:
                results.append({"url": u, "ok": False, "text": "",
                                "error": f"{type(e).__name__}: {e}", "fetched_at": fetched_at})
            print(f" crawl {'OK ' if results[-1]['ok'] else 'FAIL'} {u}", file=sys.stderr)
    return results


def crawl_urls(urls: list[str]) -> list[dict]:
    return asyncio.run(_crawl_async(urls))


def build_evidence(crawl_results: list[dict]) -> list[dict]:
    evidence = []
    for r in crawl_results:
        if not r["ok"]:
            continue
        brand = _brand_for(r["url"])
        evidence.append({
            "id": f"E{len(evidence) + 1:03d}",
            "url": r["url"],
            "excerpt": r["text"][:EXCERPT_CHARS],
            "brand": brand,
            "source_type": "official" if brand else "web",
            "fetched_at": r["fetched_at"],
        })
    return evidence


def collect() -> tuple[list[dict], list[dict]]:
    discovered = discover_urls()
    urls = select_urls(discovered)
    results = crawl_urls(urls)
    return results, build_evidence(results)


def _offline_check() -> None:
    assert _canonical("https://Example.com/a/?x=1") == "https://example.com/a"
    assert _brand_for("https://www.quince.com/women/cashmere/x") == "Quince"
    assert _brand_for("https://blog.naver.com/foo") is None
    urls = select_urls([{"url": f"https://site{i}.com/p", "found_via": "q"} for i in range(30)])
    assert len(urls) <= config.MAX_CRAWL_URLS
    fake = [{"url": "https://www.quince.com/w", "ok": True, "text": "x" * 600,
             "error": None, "fetched_at": "t"},
            {"url": "https://a.com", "ok": False, "text": "", "error": "e", "fetched_at": "t"}]
    ev = build_evidence(fake)
    assert len(ev) == 1 and ev[0]["id"] == "E001" and ev[0]["source_type"] == "official"
    print("collect offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
    else:
        limit = 3 if "--limit3" in sys.argv else None
        config.OUT_DIR.mkdir(exist_ok=True)
        if limit:
            urls = [b.url for b in config.BRANDS if b.auto_collect][:limit]
            results = crawl_urls(urls)
            evidence = build_evidence(results)
        else:
            results, evidence = collect()
        (config.OUT_DIR / "crawl_results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        (config.OUT_DIR / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = sum(r["ok"] for r in results)
        print(f"crawled ok={ok}/{len(results)} evidence={len(evidence)}")
```

- [ ] **Step 2: 오프라인 셀프체크**

Run: `.venv/bin/python -m poc.collect --offline`
Expected: `collect offline checks OK`

- [ ] **Step 3: 크롤링 스모크 (공식몰 3개만)**

Run: `.venv/bin/python -m poc.collect --limit3`
Expected: `crawled ok=N/3 evidence=N` (N≥1). `out/crawl_results.json`, `out/evidence.json` 생성. 3개 전부 실패면 crawl4ai 설치 상태(`crawl4ai-doctor`) 확인 후 재시도.

- [ ] **Step 4: Commit**

```bash
git add poc/collect.py
git commit -m "feat: Tavily 검색 + Crawl4AI 수집 + evidence 생성

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: analyze.py — LLM 2패스

**Files:**
- Create: `poc/analyze.py`

**Interfaces:**
- Consumes: `config.ANALYSIS`, `config.BRANDS`, evidence(list[dict], Task 3 형식), naver signals(list[dict], Task 2 형식), env `ANTHROPIC_API_KEY`
- Produces:
  - pydantic 모델: `ResearcherOutput{facts: [Fact{statement, evidence_ids, brand?}]}`, `AnalysisOutput{trends: [Trend{name, phase, rationale, evidence_ids}], design_map: [DesignMapRow{brand, key_items, colors, materials, silhouettes, details, price_range, evidence_ids}], gaps: [str], actions: [Action{recommendation, rationale, evidence_ids}], limitations: [str]}`
  - `run_researcher(evidence: list[dict], signals: list[dict]) -> ResearcherOutput`
  - `run_analyst(researcher: ResearcherOutput, evidence: list[dict], signals: list[dict]) -> AnalysisOutput`

- [ ] **Step 1: `poc/analyze.py` 작성**

```python
"""LLM 2패스: 리서처(사실 정리) → MD 분석가(트렌드/Design Map/액션)."""
import json
import sys
from typing import Literal

import anthropic
from pydantic import BaseModel

from poc import config

MODEL = "claude-opus-4-8"


class Fact(BaseModel):
    statement: str
    evidence_ids: list[str]
    brand: str | None = None


class ResearcherOutput(BaseModel):
    facts: list[Fact]


class Trend(BaseModel):
    name: str
    phase: Literal["상승", "주류", "포화", "둔화"]
    rationale: str
    evidence_ids: list[str]


class DesignMapRow(BaseModel):
    brand: str
    key_items: str
    colors: str
    materials: str
    silhouettes: str
    details: str
    price_range: str
    evidence_ids: list[str]


class Action(BaseModel):
    recommendation: str
    rationale: str
    evidence_ids: list[str]


class AnalysisOutput(BaseModel):
    trends: list[Trend]
    design_map: list[DesignMapRow]
    gaps: list[str]
    actions: list[Action]
    limitations: list[str]


EVIDENCE_RULE = (
    "근거 규칙: 모든 주장과 셀에는 반드시 입력으로 제공된 evidence id(E001 형식)만 인용한다. "
    "근거가 없는 항목은 값에 '근거 없음'이라고 쓰고 evidence_ids는 빈 배열로 둔다. "
    "id를 지어내지 않는다. NAVER ratio는 상대값이므로 서로 다른 요청 간 절대 비교하지 않는다."
)


def _call(system: str, user: str, output_format):
    client = anthropic.Anthropic()
    last_err = None
    for _ in range(2):  # 1회 + 스키마 실패 시 재시도 1회 (POC_SPEC §7)
        try:
            resp = client.messages.parse(
                model=MODEL,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_format,
            )
            if resp.parsed_output is None:
                raise ValueError(f"파싱 실패 stop_reason={resp.stop_reason}")
            return resp.parsed_output
        except Exception as e:
            last_err = e
    raise last_err


def _payload(evidence: list[dict], signals: list[dict]) -> str:
    return json.dumps({
        "analysis_conditions": config.ANALYSIS,
        "brands": [{"name": b.name, "purpose": b.purpose} for b in config.BRANDS if b.auto_collect],
        "naver_signals": signals,
        "evidence": evidence,
    }, ensure_ascii=False)


def run_researcher(evidence: list[dict], signals: list[dict]) -> ResearcherOutput:
    system = (
        "너는 패션 리서처다. 수집된 웹 발췌와 NAVER 수요 신호에서 사실만 정리한다. "
        "해석/추측 금지 — 발췌에 실제로 나타난 상품명, 소재, 컬러, 실루엣, 가격, 수치를 "
        "간결한 사실 문장으로 추출한다. 중복은 병합한다. " + EVIDENCE_RULE
    )
    return _call(system, _payload(evidence, signals), ResearcherOutput)


def run_analyst(researcher: ResearcherOutput, evidence: list[dict],
                signals: list[dict]) -> AnalysisOutput:
    system = (
        "너는 여성 캐시미어·니트웨어 브랜드의 MD 분석가 겸 에디터다. "
        "리서처가 정리한 사실과 원본 근거를 바탕으로 다음을 작성한다: "
        "(1) 트렌드(상승/주류/포화/둔화 구분), (2) Design Map — 브랜드별 핵심 아이템/컬러/소재/"
        "실루엣/디테일/가격대 매트릭스, 자동수집 브랜드 11개 각각 한 행씩, "
        "(3) 상품 구성 공백(gaps), (4) 실행 가능한 MD 액션 3개 이상, (5) 데이터 한계(limitations). "
        "타깃(한국 여성 25~39세)과 가격대(20만~70만원) 적합성을 항상 고려한다. "
        "근거 약한 주장은 액션에 넣지 말고 limitations에 '추가 조사 필요'로 내린다. " + EVIDENCE_RULE
    )
    user = json.dumps({"researcher_facts": researcher.model_dump()}, ensure_ascii=False) \
        + "\n\n" + _payload(evidence, signals)
    return _call(system, user, AnalysisOutput)


if __name__ == "__main__":
    config.OUT_DIR.mkdir(exist_ok=True)
    if "--fixture" in sys.argv:
        evidence = [
            {"id": "E001", "url": "https://extreme-cashmere.com/", "brand": "Extreme cashmere",
             "source_type": "official", "fetched_at": "2026-07-20",
             "excerpt": "n°316 lana sweater, brushed cashmere, colors: lilac, pistachio, tomato. €420. Oversized unisex fit."},
            {"id": "E002", "url": "https://www.quince.com/women/cashmere", "brand": "Quince",
             "source_type": "official", "fetched_at": "2026-07-20",
             "excerpt": "Mongolian Cashmere Crewneck Sweater $49.90. 100% grade-A cashmere. Classic fit, 20 colors."},
        ]
        signals = [{"source": "shopping_keyword", "group": "캐시미어니트",
                    "series": [{"period": "2026-06-01", "ratio": 100.0}],
                    "requested_segment": "25-39", "observed_segment": "20-39",
                    "coverage_mismatch": True, "note": "상대값"}]
    else:
        evidence = json.loads((config.OUT_DIR / "evidence.json").read_text(encoding="utf-8"))
        naver = json.loads((config.OUT_DIR / "naver_raw.json").read_text(encoding="utf-8"))
        signals = naver["signals"]
    r = run_researcher(evidence, signals)
    (config.OUT_DIR / "researcher.json").write_text(
        r.model_dump_json(indent=2), encoding="utf-8")
    print(f"researcher facts={len(r.facts)}")
    a = run_analyst(r, evidence, signals)
    (config.OUT_DIR / "analysis.json").write_text(
        a.model_dump_json(indent=2), encoding="utf-8")
    print(f"analyst trends={len(a.trends)} rows={len(a.design_map)} actions={len(a.actions)}")
```

- [ ] **Step 2: fixture 스모크 (실 API 호출, 소액)**

Run: `.venv/bin/python -m poc.analyze --fixture`
Expected: `researcher facts=N` (N≥2), `analyst trends=... actions=...` 출력. `out/researcher.json`, `out/analysis.json` 생성. `out/analysis.json` 열어서 evidence_ids가 E001/E002만 인용하는지, 근거 없는 브랜드 행이 "근거 없음"인지 눈으로 확인.

- [ ] **Step 3: Commit**

```bash
git add poc/analyze.py
git commit -m "feat: LLM 2패스 분석 (리서처 + MD분석가, 근거 ID 강제)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: report.py — Markdown 렌더러

**Files:**
- Create: `poc/report.py`

**Interfaces:**
- Consumes: `AnalysisOutput`, `ResearcherOutput` (Task 4), naver result dict (Task 2), crawl_results/evidence (Task 3)
- Produces: `render_report(analysis: AnalysisOutput, naver: dict, crawl_results: list[dict], evidence: list[dict]) -> str`

- [ ] **Step 1: `poc/report.py` 작성**

```python
"""Markdown 보고서 렌더러. 코드가 렌더링 — LLM 자유 생성 금지 (POC_SPEC §6)."""
import sys
from datetime import date

from poc import config
from poc.analyze import AnalysisOutput

RATIO_WARNING = ("> **주의:** NAVER ratio는 각 요청 결과의 최대값을 100으로 둔 상대값입니다. "
                 "서로 다른 요청의 값을 절대량처럼 비교할 수 없습니다.")
COVERAGE_WARNING = ("> **주의:** Shopping Insight는 25~39세를 정확히 표현할 수 없어 "
                    "20~39세(coverage_mismatch) 데이터입니다.")


def _ids(evidence_ids: list[str]) -> str:
    return ", ".join(evidence_ids) if evidence_ids else "근거 없음"


def render_report(analysis: AnalysisOutput, naver: dict,
                  crawl_results: list[dict], evidence: list[dict]) -> str:
    L: list[str] = []
    a = config.ANALYSIS
    L.append(f"# 캐시미어·니트웨어 트렌드 보고서 (PoC)\n")
    L.append(f"- 생성일: {date.today().isoformat()}")
    L.append(f"- 조건: {a['category']} / {a['target']} / {a['price_range']} / 최근 {a['period_weeks']}주")
    L.append(f"- 중점: {a['focus']}\n")

    L.append("## 1. 핵심 요약\n")
    for t in analysis.trends[:3]:
        L.append(f"- [{t.phase}] {t.name} ({_ids(t.evidence_ids)})")
    for act in analysis.actions[:3]:
        L.append(f"- 액션: {act.recommendation} ({_ids(act.evidence_ids)})")
    L.append("")

    L.append("## 2. 수요 신호 (NAVER)\n")
    L.append(RATIO_WARNING)
    signals = naver.get("signals", [])
    if any(s["coverage_mismatch"] for s in signals):
        L.append(COVERAGE_WARNING)
    L.append("")
    for s in signals:
        series = s["series"]
        if not series:
            continue
        latest, peak = series[-1], max(series, key=lambda d: d["ratio"])
        L.append(f"- **{s['group']}** ({s['source']}, {s['observed_segment']}세): "
                 f"최근 {latest['period']} ratio {latest['ratio']}, "
                 f"기간 내 최고 {peak['period']} ratio {peak['ratio']}")
    if not signals:
        L.append("- NAVER 신호 없음 (수집 실패 — 11절 참고)")
    L.append("")

    L.append("## 3. Design Map\n")
    L.append("| 브랜드 | 핵심 아이템 | 컬러 | 소재 | 실루엣 | 디테일 | 가격대 | 근거 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in analysis.design_map:
        L.append(f"| {r.brand} | {r.key_items} | {r.colors} | {r.materials} | "
                 f"{r.silhouettes} | {r.details} | {r.price_range} | {_ids(r.evidence_ids)} |")
    L.append("")

    L.append("## 4. 트렌드\n")
    for phase in ("상승", "주류", "포화", "둔화"):
        items = [t for t in analysis.trends if t.phase == phase]
        if items:
            L.append(f"### {phase}")
            for t in items:
                L.append(f"- **{t.name}**: {t.rationale} ({_ids(t.evidence_ids)})")
            L.append("")

    L.append("## 5. 상품 구성 공백과 기회\n")
    for g in analysis.gaps:
        L.append(f"- {g}")
    L.append("")

    L.append("## 6. MD 추천 액션\n")
    for i, act in enumerate(analysis.actions, 1):
        L.append(f"{i}. **{act.recommendation}** — {act.rationale} ({_ids(act.evidence_ids)})")
    L.append("")

    L.append("## 7. 데이터 한계와 수집 실패\n")
    for lim in analysis.limitations:
        L.append(f"- {lim}")
    failed = [r for r in crawl_results if not r["ok"]]
    if failed:
        L.append(f"\n수집 실패 URL {len(failed)}건:")
        for r in failed:
            L.append(f"- {r['url']} — {r['error']}")
    for f in naver.get("failures", []):
        L.append(f"- NAVER {f['call']} 실패 — {f['error']}")
    L.append("- PLUSH'MERE: Instagram — SNS 자동 수집 제외 (reference_only)")
    L.append("")

    L.append("## 8. 출처\n")
    L.append("| ID | URL | 브랜드 | 수집일 |")
    L.append("|---|---|---|---|")
    for e in evidence:
        L.append(f"| {e['id']} | {e['url']} | {e.get('brand') or '-'} | {e['fetched_at'][:10]} |")
    L.append("")
    return "\n".join(L)


def _offline_check() -> None:
    from poc.analyze import Action, AnalysisOutput, DesignMapRow, Trend
    analysis = AnalysisOutput(
        trends=[Trend(name="브러시드 캐시미어", phase="상승", rationale="r", evidence_ids=["E001"])],
        design_map=[DesignMapRow(brand="Quince", key_items="크루넥", colors="근거 없음",
                                 materials="캐시미어100", silhouettes="클래식", details="근거 없음",
                                 price_range="$49.90", evidence_ids=["E002"])],
        gaps=["컬러블록 부재"],
        actions=[Action(recommendation="a", rationale="b", evidence_ids=["E001"])],
        limitations=["표본 작음 — 추가 조사 필요"])
    naver = {"signals": [{"source": "shopping_keyword", "group": "캐시미어니트",
                          "series": [{"period": "2026-06-01", "ratio": 100.0}],
                          "requested_segment": "25-39", "observed_segment": "20-39",
                          "coverage_mismatch": True, "note": ""}],
             "failures": [{"call": "search_trend", "error": "401"}]}
    crawl = [{"url": "https://x.com", "ok": False, "text": "", "error": "timeout", "fetched_at": "t"}]
    ev = [{"id": "E001", "url": "https://extreme-cashmere.com/", "brand": "Extreme cashmere",
           "source_type": "official", "fetched_at": "2026-07-20T00:00:00"}]
    md = render_report(analysis, naver, crawl, ev)
    assert "상대값" in md, "ratio 주의문 누락"
    assert "20~39세" in md, "coverage_mismatch 주의문 누락"
    assert "근거 없음" in md
    assert "PLUSH'MERE" in md
    assert "https://x.com" in md and "timeout" in md, "실패 URL 누락"
    assert "| E001 |" in md, "출처 테이블 누락"
    print("report offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
```

- [ ] **Step 2: 오프라인 셀프체크**

Run: `.venv/bin/python -m poc.report --offline`
Expected: `report offline checks OK`

- [ ] **Step 3: Commit**

```bash
git add poc/report.py
git commit -m "feat: Markdown 보고서 렌더러 (코드 렌더, 주의문/실패 표시 강제)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: run.py — entry point + 전체 실행

**Files:**
- Create: `poc/run.py`

**Interfaces:**
- Consumes: 모든 이전 모듈
- Produces: `out/naver_raw.json`, `out/crawl_results.json`, `out/evidence.json`, `out/researcher.json`, `out/analysis.json`, `out/report.md`

- [ ] **Step 1: `poc/run.py` 작성**

```python
"""PoC 전체 파이프라인. python -m poc.run"""
import json
import sys

from poc import collect, config, naver, report
from poc.analyze import run_analyst, run_researcher


def _dump(name: str, data) -> None:
    (config.OUT_DIR / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    config.OUT_DIR.mkdir(exist_ok=True)

    print("[1/4] NAVER 수요 신호 수집...")
    try:
        naver_result = naver.fetch_all()
    except Exception as e:  # 인증키 부재 등 — 부분 실패로 계속 진행
        naver_result = {"raw": {}, "signals": [],
                        "failures": [{"call": "all", "error": f"{type(e).__name__}: {e}"}]}
    _dump("naver_raw.json", naver_result)
    print(f"  signals={len(naver_result['signals'])} failures={len(naver_result['failures'])}")

    print("[2/4] 웹 검색 + 크롤링...")
    crawl_results, evidence = collect.collect()
    _dump("crawl_results.json", crawl_results)
    _dump("evidence.json", evidence)
    ok = sum(r["ok"] for r in crawl_results)
    print(f"  crawled ok={ok}/{len(crawl_results)} evidence={len(evidence)}")
    if not evidence and not naver_result["signals"]:
        print("근거 0건 — 분석 불가. 실패 기록만 보고서에 남기고 종료.", file=sys.stderr)

    print("[3/4] LLM 분석 (2패스)...")
    researcher = run_researcher(evidence, naver_result["signals"])
    (config.OUT_DIR / "researcher.json").write_text(
        researcher.model_dump_json(indent=2), encoding="utf-8")
    analysis = run_analyst(researcher, evidence, naver_result["signals"])
    (config.OUT_DIR / "analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8")
    print(f"  facts={len(researcher.facts)} trends={len(analysis.trends)} "
          f"actions={len(analysis.actions)}")

    print("[4/4] 보고서 렌더링...")
    md = report.render_report(analysis, naver_result, crawl_results, evidence)
    (config.OUT_DIR / "report.md").write_text(md, encoding="utf-8")
    print(f"완료: {config.OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 전체 live 실행**

Run: `.venv/bin/python -m poc.run`
Expected: 4단계 진행 로그 후 `완료: .../out/report.md`. 크롤링 20 URL × 최대 60초라 총 수 분~15분 걸릴 수 있음.

- [ ] **Step 3: 성공 기준 점검 (POC_SPEC §10)**

- [ ] `out/report.md` 존재
- [ ] NAVER 신호 ≥1 포함 **또는** 실패 이유가 §7절에 표시됨
- [ ] 수집 성공 URL ≥5 (`out/crawl_results.json`에서 `ok:true` 개수)
- [ ] Design Map 셀과 MD 액션에 근거 ID 또는 "근거 없음" 표기
- [ ] 수집 실패 URL과 원인이 보고서에 나옴

미달 항목 있으면 원인(키워드? cat_id? 크롤 차단?)을 기록하고 수정 후 재실행.

- [ ] **Step 4: Commit**

```bash
git add poc/run.py
git commit -m "feat: PoC 파이프라인 entry point (run.py)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: 오너 판정**

`out/report.md`를 오너(MD)에게 전달 — "이 보고서가 실제 상품 기획에 쓸모 있는가" 판정. 결과에 따라 POC_SPEC §11 (MVP 착수 vs SPEC 수정) 진행.

---

## 리스크 메모 (실행자 참고)

- `SHOPPING_CAT_ID = "50000804"`은 **추정값**. Task 2 Step 3에서 반드시 검증. 틀려도 파이프라인은 죽지 않고 failures에 기록됨.
- NAVER API HUB는 NCP 콘솔에서 상품 구독이 되어 있어야 함. 401/403은 코드가 아니라 구독/키 문제.
- 공식몰 중 JS 헤비 사이트(COS, Quince)는 Crawl4AI로 본문 500자를 못 넘길 수 있음 — PoC에선 실패 기록으로 충분 (Browser Use fallback은 스코프 밖).
- `anthropic` SDK의 `messages.parse` + `output_format` + `thinking adaptive` 조합에서 버전에 따라 시그니처가 다를 수 있음. 에러 나면 `output_config={"format": ...}` 원시 스키마 방식으로 폴백하지 말고 SDK 버전을 올릴 것 (`pip install -U anthropic`).
```
