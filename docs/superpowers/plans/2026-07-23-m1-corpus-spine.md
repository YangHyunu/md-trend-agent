# M1 Corpus Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SPEC_V3 §12 M1 — RSS 수집(daily poll + dedup 누적) + LLM#1 코퍼스 경계(기사+웹서치 → 검증된 concepts JSON)를 구축한다.

**Architecture:** 결정론 수집 모듈 `poc/rss.py`(fetch→parse→filter→jsonl 누적)와 LLM 경계 모듈 `poc/corpus.py`(입력 번들 조립 → `poc/analyze._call` 재사용 LLM#1 호출 → 결정론 validator)를 신설한다. 웹서치는 기존 Tavily 산출물(`out/crawl_results.json`)을 재사용하고 새 수집기를 만들지 않는다. 저장은 M1에서는 `out/articles.jsonl`(M4에서 sqlite 3테이블로 이관).

**Tech Stack:** Python ≥3.11, httpx, feedparser(신규 의존성), pydantic v2, anthropic SDK(`messages.parse`), pytest + httpx.MockTransport.

## Global Constraints

- Python ≥3.11, HTTP는 httpx만 사용(requests 금지) — 기존 코드베이스 관례.
- LLM 호출은 `poc/analyze.py:81`의 `_call(system, user, output_format)` 재사용. 모델 `claude-opus-4-8`(`poc/analyze.py:11`), API 키는 SDK가 `ANTHROPIC_API_KEY` env로 읽음.
- 결정론 원칙(SPEC_V3 §3.1): fetch/파싱/필터/저장/validator에 LLM 금지. LLM은 `run_corpus` 내부 `_call` 1곳뿐.
- `naver_queries`는 한국어(한글 포함) 필수 — 한글 쿼리 0개인 concept은 폐기(SPEC_V3 §6.3).
- concept 상한 `MAX_CONCEPTS = 20` (V2 §21.2 LLM context 예산에서 파생). 상한은 프롬프트에도 명시하고 validator도 강제하되 초과 폐기분은 사유와 함께 로그(SPEC_V3 §6.3).
- 테스트는 네트워크 금지: httpx.MockTransport + `tests/poc/fixtures/` XML/JSON fixture. 기존 관례는 `tests/datalayer/test_shopify.py` 참조(모듈 레벨 헬퍼, `@pytest.fixture` 미사용).
- env 로딩: `poc/config.py`가 import 시 `load_dotenv(ROOT/".env")` 수행(`config.py:9`) — 신규 모듈은 `from poc import config`만 하면 됨.
- 커밋 메시지: 기존 스타일 `feat(poc): 한국어 요약 (SPEC_V3 §N)` + trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: RSS 피드 파서 (`parse_feed`)

**Files:**
- Modify: `requirements.txt` (feedparser 추가)
- Create: `poc/rss.py`
- Create: `tests/poc/fixtures/wwd_cashmere_feed.xml`
- Test: `tests/poc/test_rss.py`

**Interfaces:**
- Consumes: 없음 (신규 모듈 시작점)
- Produces: `parse_feed(xml_text: str, source: str) -> list[dict]` — article dict 키: `id`(url sha1 앞 10자리, `a` 접두), `source`, `url`, `title`, `published_at`(ISO8601 UTC 또는 None), `fetched_at`(ISO8601 UTC), `matched_terms`(list, 여기서는 빈 리스트), `excerpt`(HTML 태그 제거, 300자 절단). 이 dict 형태가 M1 전체와 M4 `articles` 테이블(SPEC_V3 §9.1)의 계약이다.

- [ ] **Step 1: 의존성 추가**

`requirements.txt`의 `python-dotenv>=1.0` 다음 줄에 추가:

```
feedparser>=6.0
```

Run: `.venv/bin/pip install feedparser`
Expected: `Successfully installed feedparser-6.x.x sgmllib3k-...`

- [ ] **Step 2: fixture 작성**

`tests/poc/fixtures/wwd_cashmere_feed.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>cashmere Archives - WWD</title>
    <link>https://wwd.com/tag/cashmere/</link>
    <item>
      <title>Cashmere Prices Climb as Supply Tightens</title>
      <link>https://wwd.com/fashion-news/cashmere-prices-climb/</link>
      <pubDate>Mon, 20 Jul 2026 09:00:00 +0000</pubDate>
      <description><![CDATA[<p>Cashmere supply from Inner Mongolia tightened this season, pushing prices up.</p>]]></description>
    </item>
    <item>
      <title>Knit Labels Bet on Pointelle for Fall</title>
      <link>https://wwd.com/fashion-news/pointelle-fall/</link>
      <pubDate>Sun, 19 Jul 2026 12:30:00 +0000</pubDate>
      <description><![CDATA[Pointelle knits return on fall runways.]]></description>
    </item>
  </channel>
</rss>
```

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/poc/test_rss.py`:

```python
from pathlib import Path

from poc.rss import parse_feed

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_feed_maps_items():
    xml = (FIXTURES / "wwd_cashmere_feed.xml").read_text()
    articles = parse_feed(xml, source="wwd:cashmere")
    assert len(articles) == 2
    first = articles[0]
    assert first["url"] == "https://wwd.com/fashion-news/cashmere-prices-climb/"
    assert first["title"] == "Cashmere Prices Climb as Supply Tightens"
    assert first["source"] == "wwd:cashmere"
    assert first["published_at"].startswith("2026-07-20")
    assert first["id"].startswith("a") and len(first["id"]) == 11
    assert "<p>" not in first["excerpt"]
    assert first["matched_terms"] == []


def test_parse_feed_skips_items_without_link():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>no link</title></item>
    </channel></rss>"""
    assert parse_feed(xml, source="wwd:wool") == []
```

- [ ] **Step 4: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'poc.rss'`

- [ ] **Step 5: 구현**

`poc/rss.py`:

```python
"""RSS 수집 — SPEC_V3 §5.1: WWD 태그피드 + 글로시 all.xml 키워드 필터."""

import hashlib
import re
import time
from datetime import datetime, timezone

import feedparser


def _article_id(url: str) -> str:
    return "a" + hashlib.sha1(url.encode()).hexdigest()[:10]


def _iso(struct: time.struct_time | None) -> str | None:
    if struct is None:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc).isoformat()


def _excerpt(entry: dict) -> str:
    raw = entry.get("summary", "") or ""
    return re.sub(r"<[^>]+>", "", raw).strip()[:300]


def parse_feed(xml_text: str, source: str) -> list[dict]:
    parsed = feedparser.parse(xml_text)
    now = datetime.now(timezone.utc).isoformat()
    articles = []
    for entry in parsed.entries:
        url = entry.get("link", "")
        if not url:
            continue
        articles.append(
            {
                "id": _article_id(url),
                "source": source,
                "url": url,
                "title": entry.get("title", ""),
                "published_at": _iso(entry.get("published_parsed")),
                "fetched_at": now,
                "matched_terms": [],
                "excerpt": _excerpt(entry),
            }
        )
    return articles
```

- [ ] **Step 6: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add requirements.txt poc/rss.py tests/poc/test_rss.py tests/poc/fixtures/wwd_cashmere_feed.xml
git commit -m "feat(poc): RSS 피드 파서 — article dict 계약 (SPEC_V3 §5.1)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 글로시 키워드 필터 (`filter_by_terms`)

**Files:**
- Modify: `poc/rss.py`
- Create: `tests/poc/fixtures/glossy_all_feed.xml`
- Test: `tests/poc/test_rss.py`

**Interfaces:**
- Consumes: Task 1의 article dict.
- Produces: `filter_by_terms(articles: list[dict], terms: list[str]) -> list[dict]` — title+excerpt 소문자 부분일치. 매칭 없는 기사 제거, 매칭 기사는 `matched_terms`에 히트 term 기록. 부분일치는 의도(recall 우선 — "woolrich"가 "wool"에 걸려도 하류 LLM#1이 판별).

- [ ] **Step 1: fixture 작성**

`tests/poc/fixtures/glossy_all_feed.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Vogue — All</title>
    <link>https://www.vogue.com/</link>
    <item>
      <title>The Cashmere Cardigans Editors Love</title>
      <link>https://www.vogue.com/article/cashmere-cardigans</link>
      <pubDate>Tue, 21 Jul 2026 08:00:00 +0000</pubDate>
      <description>Soft cashmere knits for the season.</description>
    </item>
    <item>
      <title>Best Sneakers of Summer</title>
      <link>https://www.vogue.com/article/best-sneakers</link>
      <pubDate>Tue, 21 Jul 2026 07:00:00 +0000</pubDate>
      <description>Nothing about yarn here.</description>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: 실패하는 테스트 추가**

`tests/poc/test_rss.py`에 추가:

```python
from poc.rss import filter_by_terms


def test_filter_by_terms_keeps_only_matches_and_records_terms():
    xml = (FIXTURES / "glossy_all_feed.xml").read_text()
    articles = parse_feed(xml, source="glossy:vogue")
    kept = filter_by_terms(articles, ["cashmere", "cardigan", "knit"])
    assert len(kept) == 1
    assert kept[0]["url"] == "https://www.vogue.com/article/cashmere-cardigans"
    assert sorted(kept[0]["matched_terms"]) == ["cardigan", "cashmere", "knit"]


def test_filter_by_terms_is_case_insensitive():
    articles = [{"title": "CASHMERE now", "excerpt": "", "matched_terms": []}]
    assert filter_by_terms(articles, ["cashmere"])[0]["matched_terms"] == ["cashmere"]
```

- [ ] **Step 3: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: FAIL — `ImportError: cannot import name 'filter_by_terms'`

- [ ] **Step 4: 구현**

`poc/rss.py`에 추가:

```python
def filter_by_terms(articles: list[dict], terms: list[str]) -> list[dict]:
    kept = []
    for a in articles:
        text = f"{a['title']} {a['excerpt']}".lower()
        matched = [t for t in terms if t in text]
        if matched:
            kept.append({**a, "matched_terms": matched})
    return kept
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add poc/rss.py tests/poc/test_rss.py tests/poc/fixtures/glossy_all_feed.xml
git commit -m "feat(poc): 글로시 all.xml 키워드 필터 (SPEC_V3 §5.1)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 피드 fetch + config 소스 목록 (`fetch_all_feeds`)

**Files:**
- Modify: `poc/config.py`
- Modify: `poc/rss.py`
- Test: `tests/poc/test_rss.py`

**Interfaces:**
- Consumes: Task 1 `parse_feed`, Task 2 `filter_by_terms`, config 신규 상수.
- Produces:
  - config 상수 `WWD_TAG_FEEDS: dict[str, str]`, `GLOSSY_FEEDS: dict[str, str]`, `KNIT_FILTER_TERMS: list[str]`, `ARTICLES_PATH: Path`, `MAX_CONCEPTS: int`.
  - `fetch_feed(client: httpx.Client, url: str) -> str | None` (실패 시 None).
  - `fetch_all_feeds(client: httpx.Client | None = None) -> dict` — `{"articles": list[dict], "failures": list[str]}`. WWD 태그피드 기사는 `matched_terms=[term]` 부여, 글로시 기사는 `KNIT_FILTER_TERMS` 필터 통과분만. 피드 하나 실패해도 진행(부분 실패 정상, SPEC_V3 §4).

- [ ] **Step 1: config 상수 추가**

`poc/config.py` 끝에 추가:

```python
# --- RSS (SPEC_V3 §5.1) ---
# WWD 태그피드가 유일한 타깃 소스. crochet/sweaters/cardigan은 WWD 태그 어휘가
# 아니라 빈 200을 반환하므로 넣지 않는다(2026-07-23 실측).
WWD_TAG_FEEDS = {
    "cashmere": "https://wwd.com/tag/cashmere/feed/",
    "knitwear": "https://wwd.com/tag/knitwear/feed/",
    "wool": "https://wwd.com/tag/wool/feed/",
}
# 글로시는 전체 피드만 살아있음(섹션 피드 전부 404) — 키워드 필터 필수.
GLOSSY_FEEDS = {
    "vogue": "https://www.vogue.com/feed/rss",
    "harpersbazaar": "https://www.harpersbazaar.com/rss/all.xml/",
    "elle": "https://www.elle.com/rss/all.xml/",
}
KNIT_FILTER_TERMS = [
    "knit", "knitwear", "cashmere", "sweater", "cardigan", "wool",
    "crochet", "pointelle", "mohair", "alpaca", "merino",
]
ARTICLES_PATH = OUT_DIR / "articles.jsonl"
MAX_CONCEPTS = 20  # LLM#1 concept 상한 (V2 §21.2 예산 파생)
```

- [ ] **Step 2: 실패하는 테스트 추가**

`tests/poc/test_rss.py`에 추가:

```python
import httpx

from poc import config
from poc.rss import fetch_all_feeds

_WWD_XML = (FIXTURES / "wwd_cashmere_feed.xml").read_text()
_GLOSSY_XML = (FIXTURES / "glossy_all_feed.xml").read_text()


def _feed_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "wwd.com":
        if "cashmere" in request.url.path:
            return httpx.Response(200, text=_WWD_XML)
        return httpx.Response(404)
    return httpx.Response(200, text=_GLOSSY_XML)


def _feed_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_feed_handler))


def test_fetch_all_feeds_tags_wwd_and_filters_glossy():
    result = fetch_all_feeds(client=_feed_client())
    wwd = [a for a in result["articles"] if a["source"] == "wwd:cashmere"]
    glossy = [a for a in result["articles"] if a["source"].startswith("glossy:")]
    assert len(wwd) == 2
    assert all(a["matched_terms"] == ["cashmere"] for a in wwd)
    # 글로시 피드 3개 모두 같은 fixture(기사 2개 중 1개만 니트 매칭)를 반환
    assert len(glossy) == 3
    assert all("cashmere" in a["matched_terms"] for a in glossy)
    # knitwear/wool 태그피드는 404 → failures에 기록, 파이프라인은 진행
    assert "wwd:knitwear" in result["failures"]
    assert "wwd:wool" in result["failures"]
```

- [ ] **Step 3: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_all_feeds'`

- [ ] **Step 4: 구현**

`poc/rss.py` 상단 import에 `import httpx`와 `from poc import config` 추가 후, 아래 추가:

```python
DEFAULT_TIMEOUT = 20.0
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) md-trend-agent/0.1"


def fetch_feed(client: httpx.Client, url: str) -> str | None:
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError:
        return None


def fetch_all_feeds(client: httpx.Client | None = None) -> dict:
    own = client is None
    if own:
        client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )
    articles: list[dict] = []
    failures: list[str] = []
    try:
        for term, url in config.WWD_TAG_FEEDS.items():
            xml = fetch_feed(client, url)
            if xml is None:
                failures.append(f"wwd:{term}")
                continue
            found = parse_feed(xml, source=f"wwd:{term}")
            articles.extend({**a, "matched_terms": [term]} for a in found)
        for name, url in config.GLOSSY_FEEDS.items():
            xml = fetch_feed(client, url)
            if xml is None:
                failures.append(f"glossy:{name}")
                continue
            found = parse_feed(xml, source=f"glossy:{name}")
            articles.extend(filter_by_terms(found, config.KNIT_FILTER_TERMS))
    finally:
        if own:
            client.close()
    return {"articles": articles, "failures": failures}
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add poc/config.py poc/rss.py tests/poc/test_rss.py
git commit -m "feat(poc): RSS 피드 fetch — WWD 태그 3종 + 글로시 3종, 부분 실패 격리 (SPEC_V3 §5.1)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: articles.jsonl 누적 저장 + daily poll CLI

**Files:**
- Modify: `poc/rss.py`
- Test: `tests/poc/test_rss.py`

**Interfaces:**
- Consumes: Task 3 `fetch_all_feeds`, `config.ARTICLES_PATH`.
- Produces:
  - `load_articles(path: Path | None = None) -> list[dict]` — jsonl 전체 로드(없으면 빈 리스트).
  - `append_articles(new: list[dict], path: Path | None = None) -> int` — URL 기준 dedup 후 append, 추가 건수 반환.
  - `poll(client: httpx.Client | None = None, path: Path | None = None) -> dict` — `{"fetched": int, "added": int, "failures": list[str]}`.
  - `python -m poc.rss` = daily poll 진입점(스케줄링은 외부 cron, Task 7에서 문서화).

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/poc/test_rss.py`에 추가:

```python
from poc.rss import append_articles, load_articles, poll


def _article(url: str) -> dict:
    return {
        "id": "a" + url[-10:],
        "source": "wwd:cashmere",
        "url": url,
        "title": "t",
        "published_at": None,
        "fetched_at": "2026-07-23T00:00:00+00:00",
        "matched_terms": ["cashmere"],
        "excerpt": "e",
    }


def test_append_articles_dedups_by_url(tmp_path):
    path = tmp_path / "articles.jsonl"
    first = append_articles([_article("https://x/1"), _article("https://x/2")], path=path)
    second = append_articles([_article("https://x/2"), _article("https://x/3")], path=path)
    assert (first, second) == (2, 1)
    assert [a["url"] for a in load_articles(path)] == ["https://x/1", "https://x/2", "https://x/3"]


def test_poll_fetches_and_appends(tmp_path):
    path = tmp_path / "articles.jsonl"
    summary = poll(client=_feed_client(), path=path)
    assert summary["added"] == len(load_articles(path)) > 0
    again = poll(client=_feed_client(), path=path)
    assert again["added"] == 0  # 같은 피드 재수집 = 전부 dedup
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: FAIL — `ImportError: cannot import name 'append_articles'`

- [ ] **Step 3: 구현**

`poc/rss.py` 상단 import에 `import json`과 `from pathlib import Path` 추가 후, 아래 추가:

```python
def load_articles(path: Path | None = None) -> list[dict]:
    path = path or config.ARTICLES_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_articles(new: list[dict], path: Path | None = None) -> int:
    path = path or config.ARTICLES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = {a["url"] for a in load_articles(path)}
    added = 0
    with path.open("a", encoding="utf-8") as fh:
        for a in new:
            if a["url"] in seen:
                continue
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
            seen.add(a["url"])
            added += 1
    return added


def poll(client: httpx.Client | None = None, path: Path | None = None) -> dict:
    result = fetch_all_feeds(client)
    added = append_articles(result["articles"], path)
    return {
        "fetched": len(result["articles"]),
        "added": added,
        "failures": result["failures"],
    }


if __name__ == "__main__":
    print(json.dumps(poll(), ensure_ascii=False))
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_rss.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add poc/rss.py tests/poc/test_rss.py
git commit -m "feat(poc): articles.jsonl URL-dedup 누적 + daily poll CLI (SPEC_V3 §5.1, §9.1)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 코퍼스 입력 번들 (`build_corpus_input`)

**Files:**
- Create: `poc/corpus.py`
- Test: `tests/poc/test_corpus.py`

**Interfaces:**
- Consumes: Task 1 article dict, `out/crawl_results.json`(기존 Tavily 산출물 — dict 리스트, 키는 `query`/`title`/`url`/`content`를 `.get`으로 방어적으로 읽음), 직전 주 concepts(dict 리스트).
- Produces: `build_corpus_input(articles: list[dict], crawl_results: list[dict], prior_concepts: list[dict], now: datetime | None = None) -> tuple[dict, set[str]]` — bundle 키: `articles`(ref=article id), `websearch`(ref=`w{i}`), `prior_concepts`(label_ko/label_en/category만). `valid_refs` = 번들에 실제 포함된 전체 ref 집합(SPEC_V3 §6.3 역추적 검증의 기준). 기사는 `fetched_at` 기준 최근 `WINDOW_DAYS=7`일만 포함(주간 누적 소비, SPEC_V3 §6.1).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/poc/test_corpus.py`:

```python
from datetime import datetime, timezone

from poc.corpus import build_corpus_input

_NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _article(url: str, fetched: str) -> dict:
    return {
        "id": "a" + url[-8:],
        "source": "wwd:cashmere",
        "url": url,
        "title": "Cashmere Prices Climb",
        "published_at": "2026-07-20T09:00:00+00:00",
        "fetched_at": fetched,
        "matched_terms": ["cashmere"],
        "excerpt": "supply tightened",
    }


def test_build_corpus_input_windows_articles_and_collects_refs():
    articles = [
        _article("https://x/fresh-01", "2026-07-22T00:00:00+00:00"),
        _article("https://x/stale-01", "2026-07-01T00:00:00+00:00"),
    ]
    crawl = [{"query": "니트 트렌드", "title": "올가을 니트", "url": "https://blog/1",
              "content": "x" * 500}]
    prior = [{"label_ko": "포인텔 니트", "label_en": "pointelle knit",
              "category": "소재", "aliases": [], "naver_queries": ["포인텔"],
              "source_refs": ["a-old"], "rationale": "지난주"}]

    bundle, valid_refs = build_corpus_input(articles, crawl, prior, now=_NOW)

    assert [a["ref"] for a in bundle["articles"]] == ["afresh-01"]
    assert bundle["websearch"][0]["ref"] == "w0"
    assert len(bundle["websearch"][0]["content"]) == 300
    assert bundle["prior_concepts"] == [
        {"label_ko": "포인텔 니트", "label_en": "pointelle knit", "category": "소재"}
    ]
    assert valid_refs == {"afresh-01", "w0"}
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'poc.corpus'`

- [ ] **Step 3: 구현**

`poc/corpus.py`:

```python
"""LLM#1 코퍼스 경계 — SPEC_V3 §6: 주간 기사+웹서치 → 검증된 concepts."""

from datetime import datetime, timedelta, timezone

WINDOW_DAYS = 7


def _recent(articles: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    return [a for a in articles if a["fetched_at"] >= cutoff]


def build_corpus_input(
    articles: list[dict],
    crawl_results: list[dict],
    prior_concepts: list[dict],
    now: datetime | None = None,
) -> tuple[dict, set[str]]:
    recent = _recent(articles, now)
    web = [
        {
            "ref": f"w{i}",
            "query": r.get("query", ""),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": (r.get("content") or "")[:300],
        }
        for i, r in enumerate(crawl_results)
    ]
    bundle = {
        "articles": [
            {
                "ref": a["id"],
                "source": a["source"],
                "title": a["title"],
                "published_at": a["published_at"],
                "matched_terms": a["matched_terms"],
                "excerpt": a["excerpt"],
            }
            for a in recent
        ],
        "websearch": web,
        "prior_concepts": [
            {"label_ko": c["label_ko"], "label_en": c["label_en"], "category": c["category"]}
            for c in prior_concepts
        ],
    }
    valid_refs = {a["ref"] for a in bundle["articles"]} | {w["ref"] for w in web}
    return bundle, valid_refs
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add poc/corpus.py tests/poc/test_corpus.py
git commit -m "feat(poc): LLM#1 입력 번들 조립 — 주간 윈도우 + ref 집합 (SPEC_V3 §6.1)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Concept 모델 + 결정론 validator (`validate_concepts`)

**Files:**
- Modify: `poc/corpus.py`
- Test: `tests/poc/test_corpus.py`

**Interfaces:**
- Consumes: Task 5 `valid_refs`, `config.MAX_CONCEPTS`.
- Produces:
  - `Concept(BaseModel)` — `label_ko: str`, `label_en: str`, `aliases: list[str]`, `category: Literal["소재","아이템","실루엣","컬러","테마"]`, `naver_queries: list[str]`, `source_refs: list[str]`, `rationale: str` (SPEC_V3 §6.2 계약 그대로).
  - `CorpusOutput(BaseModel)` — `concepts: list[Concept]`. LLM `output_format`으로 사용.
  - `validate_concepts(output: CorpusOutput, valid_refs: set[str], max_concepts: int | None = None) -> tuple[list[Concept], list[dict]]` — 폐기 사유: `no_valid_source_refs`(실존 ref 0개), `no_korean_query`(한글 쿼리 0개), `over_max_concepts`(상한 초과). 통과 concept은 무효 ref/비한글 쿼리를 제거한 사본. dropped 항목: `{"label_ko": ..., "reason": ...}`.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/poc/test_corpus.py`에 추가:

```python
from poc.corpus import Concept, CorpusOutput, validate_concepts


def _concept(**over) -> Concept:
    base = dict(
        label_ko="포인텔 니트", label_en="pointelle knit", aliases=["pointelle"],
        category="소재", naver_queries=["포인텔", "pointelle"],
        source_refs=["afresh-01"], rationale="WWD 언급",
    )
    return Concept(**{**base, **over})


def test_validate_drops_unknown_refs_and_trims():
    out = CorpusOutput(concepts=[
        _concept(),
        _concept(label_ko="유령 개념", source_refs=["ghost-ref"]),
    ])
    kept, dropped = validate_concepts(out, {"afresh-01"})
    assert [c.label_ko for c in kept] == ["포인텔 니트"]
    assert kept[0].source_refs == ["afresh-01"]
    assert kept[0].naver_queries == ["포인텔"]  # 비한글 쿼리 제거
    assert dropped == [{"label_ko": "유령 개념", "reason": "no_valid_source_refs"}]


def test_validate_drops_concepts_without_korean_query():
    out = CorpusOutput(concepts=[_concept(naver_queries=["pointelle knit"])])
    kept, dropped = validate_concepts(out, {"afresh-01"})
    assert kept == []
    assert dropped[0]["reason"] == "no_korean_query"


def test_validate_caps_at_max_concepts():
    out = CorpusOutput(concepts=[_concept(label_ko=f"개념{i}") for i in range(5)])
    kept, dropped = validate_concepts(out, {"afresh-01"}, max_concepts=3)
    assert len(kept) == 3
    assert [d["reason"] for d in dropped] == ["over_max_concepts"] * 2
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py -v`
Expected: FAIL — `ImportError: cannot import name 'Concept'`

- [ ] **Step 3: 구현**

`poc/corpus.py` 상단 import 교체/추가:

```python
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from poc import config
```

모듈에 추가:

```python
class Concept(BaseModel):
    label_ko: str
    label_en: str
    aliases: list[str] = Field(default_factory=list)
    category: Literal["소재", "아이템", "실루엣", "컬러", "테마"]
    naver_queries: list[str]
    source_refs: list[str]
    rationale: str


class CorpusOutput(BaseModel):
    concepts: list[Concept]


_HANGUL = re.compile(r"[가-힣]")


def validate_concepts(
    output: CorpusOutput,
    valid_refs: set[str],
    max_concepts: int | None = None,
) -> tuple[list[Concept], list[dict]]:
    max_concepts = max_concepts or config.MAX_CONCEPTS
    kept: list[Concept] = []
    dropped: list[dict] = []
    for c in output.concepts:
        refs = [r for r in c.source_refs if r in valid_refs]
        if not refs:
            dropped.append({"label_ko": c.label_ko, "reason": "no_valid_source_refs"})
            continue
        queries = [q for q in c.naver_queries if _HANGUL.search(q)]
        if not queries:
            dropped.append({"label_ko": c.label_ko, "reason": "no_korean_query"})
            continue
        kept.append(c.model_copy(update={"source_refs": refs, "naver_queries": queries}))
    if len(kept) > max_concepts:
        for c in kept[max_concepts:]:
            dropped.append({"label_ko": c.label_ko, "reason": "over_max_concepts"})
        kept = kept[:max_concepts]
    return kept, dropped
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add poc/corpus.py tests/poc/test_corpus.py
git commit -m "feat(poc): Concept 계약 + 결정론 validator — 역추적/한글쿼리/상한 (SPEC_V3 §6.2-6.3)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: LLM#1 호출 + weekly CLI (`run_corpus`, `python -m poc.corpus`)

**Files:**
- Modify: `poc/corpus.py`
- Test: `tests/poc/test_corpus.py`

**Interfaces:**
- Consumes: `poc.analyze._call(system, user, output_format)` (`poc/analyze.py:81` — retry·sanitize 내장), Task 5 번들, Task 6 모델/validator, `poc.rss.load_articles`.
- Produces:
  - `run_corpus(bundle: dict, valid_refs: set[str]) -> tuple[list[Concept], list[dict]]` — 유일한 LLM 호출 지점.
  - `main() -> dict` — 입력: `config.ARTICLES_PATH`, `out/crawl_results.json`(없으면 `[]`), `out/concepts.json`(직전 주, 없으면 `[]`). 출력: `out/concepts.json`(list[dict]) + `out/concepts_dropped.json`. LLM 실패 시 직전 주 concepts.json을 건드리지 않고 `{"fallback": "<사유>"}` 반환(SPEC_V3 §4 실패 격리).
  - `python -m poc.corpus` = weekly run의 코퍼스 단계 진입점(M2가 이 출력을 소비).

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/poc/test_corpus.py`에 추가:

```python
import json

from poc import config, corpus


def _seed_articles(monkeypatch, tmp_path):
    articles_path = tmp_path / "articles.jsonl"
    articles_path.write_text(
        json.dumps(_article("https://x/fresh-01", "2026-07-22T00:00:00+00:00")) + "\n"
    )
    monkeypatch.setattr(config, "ARTICLES_PATH", articles_path)
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)


def test_main_writes_validated_concepts(monkeypatch, tmp_path):
    _seed_articles(monkeypatch, tmp_path)
    monkeypatch.setattr(
        corpus, "_call",
        lambda system, user, fmt: CorpusOutput(concepts=[
            _concept(),
            _concept(label_ko="유령", source_refs=["ghost"]),
        ]),
    )

    summary = corpus.main(now=_NOW)

    saved = json.loads((tmp_path / "concepts.json").read_text())
    dropped = json.loads((tmp_path / "concepts_dropped.json").read_text())
    assert summary == {"concepts": 1, "dropped": 1}
    assert saved[0]["label_ko"] == "포인텔 니트"
    assert dropped[0]["reason"] == "no_valid_source_refs"


def test_main_falls_back_to_prior_on_llm_failure(monkeypatch, tmp_path):
    _seed_articles(monkeypatch, tmp_path)
    prior = [_concept().model_dump()]
    (tmp_path / "concepts.json").write_text(json.dumps(prior, ensure_ascii=False))

    def _boom(system, user, fmt):
        raise RuntimeError("api down")

    monkeypatch.setattr(corpus, "_call", _boom)

    summary = corpus.main(now=_NOW)

    assert summary["fallback"] == "api down"
    assert summary["concepts"] == 1
    # 직전 주 파일은 무변경
    assert json.loads((tmp_path / "concepts.json").read_text()) == prior
```

`_article`는 이 파일 상단에서 이미 정의됨(Task 5 Step 1).

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py -v`
Expected: FAIL — `AttributeError: module 'poc.corpus' has no attribute '_call'` (또는 `main` 부재)

- [ ] **Step 3: 구현**

`poc/corpus.py` 상단 import에 추가:

```python
import json

from poc.analyze import _call
from poc.rss import load_articles
```

모듈에 추가:

```python
CORPUS_SYSTEM = """너는 캐시미어·니트웨어 MD를 위한 트렌드 코퍼스 큐레이터다.
입력 JSON에는 최근 1주 패션 에디토리얼 기사(articles), 웹서치 결과(websearch),
직전 주 개념 목록(prior_concepts)이 있다.

임무: 측정할 가치가 있는 트렌드 개념을 최대 {max_concepts}개 추출한다.

규칙:
- 각 개념의 source_refs에는 근거가 된 articles/websearch 항목의 ref 값만 넣는다.
  입력에 없는 ref를 지어내면 그 개념은 폐기된다.
- naver_queries는 한국 소비자가 실제 검색할 한국어 검색어 1~3개.
  한국어 쿼리가 없으면 그 개념은 폐기된다.
- category는 소재/아이템/실루엣/컬러/테마 중 하나.
- prior_concepts에 있던 개념도 이번 주 근거가 있으면 다시 포함한다(연속 측정).
- 일반어(니트, 스웨터 단독)보다 구체 개념(포인텔 니트, 크롭 카디건)을 우선한다.
"""


def run_corpus(bundle: dict, valid_refs: set[str]) -> tuple[list[Concept], list[dict]]:
    raw = _call(
        CORPUS_SYSTEM.format(max_concepts=config.MAX_CONCEPTS),
        json.dumps(bundle, ensure_ascii=False),
        CorpusOutput,
    )
    return validate_concepts(raw, valid_refs)


def main(now: datetime | None = None) -> dict:
    articles = load_articles()
    crawl_path = config.OUT_DIR / "crawl_results.json"
    crawl = json.loads(crawl_path.read_text()) if crawl_path.exists() else []
    prior_path = config.OUT_DIR / "concepts.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else []

    bundle, valid_refs = build_corpus_input(articles, crawl, prior, now=now)
    try:
        kept, dropped = run_corpus(bundle, valid_refs)
    except Exception as exc:
        # LLM#1 실패 → 직전 주 concepts 유지 (SPEC_V3 §4 실패 격리)
        return {"concepts": len(prior), "dropped": 0, "fallback": str(exc)}

    concepts = [c.model_dump() for c in kept]
    prior_path.write_text(json.dumps(concepts, ensure_ascii=False, indent=2))
    (config.OUT_DIR / "concepts_dropped.json").write_text(
        json.dumps(dropped, ensure_ascii=False, indent=2)
    )
    return {"concepts": len(concepts), "dropped": len(dropped)}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/pytest tests/poc/test_corpus.py -v`
Expected: 6 passed

- [ ] **Step 5: 전체 회귀 확인**

Run: `.venv/bin/pytest tests/ -x -q --ignore=tests/test_live_pipeline.py`
Expected: 기존 전체 + 신규 13개 모두 passed

- [ ] **Step 6: Commit**

```bash
git add poc/corpus.py tests/poc/test_corpus.py
git commit -m "feat(poc): LLM#1 코퍼스 호출 + weekly CLI, 실패시 직전주 fallback (SPEC_V3 §6, §4)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 라이브 검증 + 스케줄 문서 (M1 수용 기준)

**Files:**
- Create: `ops/cron.md`

**Interfaces:**
- Consumes: Task 4 `python -m poc.rss`, Task 7 `python -m poc.corpus`.
- Produces: M1 수용 판정(SPEC_V3 §12 M1 행) + daily/weekly 스케줄 문서.

**주의: LLM-in-loop 구간 — green 단위 테스트가 runtime FAIL을 가릴 수 있다(SPEC_V3 §13). 이 태스크의 라이브 run이 수용 기준이다. 결과가 나쁘면 CORPUS_SYSTEM 프롬프트를 튜닝하고 재실행한다(코드 구조 변경 아님).**

- [ ] **Step 1: RSS 라이브 poll**

Run: `.venv/bin/python -m poc.rss`
Expected: `{"fetched": N, "added": M, "failures": [...]}` — `fetched > 0`, WWD 태그 3종 중 최소 1종 성공(`failures`에 wwd 3종 전부가 있으면 안 됨). 글로시는 404/차단 가능 — failures 기록만 확인.

- [ ] **Step 2: 누적 확인**

Run: `wc -l out/articles.jsonl && head -1 out/articles.jsonl`
Expected: 라인 수 = Step 1의 `added`, 첫 라인에 `"id": "a...`, `"matched_terms"` 필드 존재.

- [ ] **Step 3: 코퍼스 라이브 run**

전제: `.env`에 `ANTHROPIC_API_KEY` 존재(기존 파이프라인이 이미 사용 중), `out/crawl_results.json`은 직전 파이프라인 run 산출물이 이미 존재.

Run: `.venv/bin/python -m poc.corpus`
Expected: `{"concepts": N, "dropped": M}` — `N ≥ 5`, fallback 키 없음.

- [ ] **Step 4: M1 수용 기준 판정 (SPEC_V3 §12 M1)**

Run: `.venv/bin/python -c "
import json
concepts = json.loads(open('out/concepts.json').read())
import re
h = re.compile(r'[가-힣]')
assert concepts, 'concepts 비어있음'
assert all(c['source_refs'] for c in concepts), 'source_refs 없는 concept 존재'
assert all(any(h.search(q) for q in c['naver_queries']) for c in concepts), '한글 쿼리 누락'
print('M1 수용 기준 통과:', len(concepts), '개 concept')
"`
Expected: `M1 수용 기준 통과: N 개 concept`

내용 품질 육안 점검: `out/concepts.json`을 열어 개념이 일반어 나열이 아닌지, `out/concepts_dropped.json`의 폐기 사유 분포가 비정상(전부 no_valid_source_refs 등)이 아닌지 확인. 비정상이면 `CORPUS_SYSTEM` 튜닝 후 Step 3부터 재실행.

- [ ] **Step 5: 스케줄 문서 작성**

`ops/cron.md`:

```markdown
# 수집·분석 스케줄 (SPEC_V3 §5)

2계층 cadence: 수집 daily / 분석 weekly. 스케줄러는 외부(cron/launchd) — 코드는
멱등 CLI만 제공한다(재실행 안전: RSS는 URL dedup, 코퍼스는 파일 덮어쓰기).

## daily — RSS poll

    0 9 * * * cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.rss >> out/rss_poll.log 2>&1

## weekly — 코퍼스 (분석 run의 1단계, M2에서 전체 파이프라인으로 확장)

    0 10 * * 1 cd /Users/yanghyeon-u/Desktop/md-trend-agent && .venv/bin/python -m poc.corpus >> out/corpus_run.log 2>&1

- weekly 요일은 config 취급(SPEC_V3 §5.2) — 현재 월요일 10:00 KST.
- LLM·API 예산은 weekly run에만 발생(V2 §21).
```

- [ ] **Step 6: Commit**

```bash
git add ops/cron.md
git commit -m "docs(ops): daily RSS / weekly 코퍼스 스케줄 (SPEC_V3 §5)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- SPEC_V3 §12 M1 수용 기준 3항목 매핑: fixture→concepts(Task 5–7 테스트), source_refs 역추적(Task 6 + Task 8 Step 4), 라이브 한국어 쿼리(Task 8 Step 3–4). 커버 완료.
- SPEC_V3 §5.1 daily poll(Task 4+8), §6.1 입력(Task 5), §6.2 계약(Task 6), §6.3 검증 3규칙(Task 6), §4 LLM#1 실패 fallback(Task 7). 커버 완료.
- M1 범위 밖(의도적 제외): NAVER 호출(M2), 저장 3테이블(M4 — M1은 jsonl), run.py 배선(M2), 한국 매체 RSS(SPEC_V3 §14).
- 타입 일관성: article dict 키 8종·Concept 필드 7종·`(bundle, valid_refs)` 튜플이 Task 1→5→6→7에서 동일 사용 확인.
