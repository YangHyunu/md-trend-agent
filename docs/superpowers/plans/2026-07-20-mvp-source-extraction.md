# MVP 데이터 레이어 #1 — 소스 획득 + 필드 추출 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 브랜드(name, homepage_url)를 받아 정규화된 상품 레코드 리스트(item·색·가격·통화·소재·신상일)를 반환하는 재사용 라이브러리 `datalayer/`를 만든다. 소스 사다리(rung1 Shopify `/products.json`)와 필드 폴백 사다리(구조화→LLM→substring 검증)를 구현한다.

**Architecture:** 프레임워크 독립 라이브러리. `run_ladder`가 소스를 순서대로 시도해 첫 성공을 채택(§12.1). 각 소스는 raw 피드를 공통 `ProductRecord`로 매핑하며, 매핑 시 `fields.py`의 공유 헬퍼(가격/아이템/색/소재)로 필드별 폴백을 적용(§12.2). 통화 변환·색계열 매핑·집계는 별도 플랜(#2/#3/#4)이 이 출력을 소비한다.

**Tech Stack:** Python 3.11+, httpx 0.28(+MockTransport 테스트), dataclasses, pytest 8(신규 dev dep). LLM 폴백은 주입형 `LLMFn` 인터페이스로 테스트 시 stub.

## Global Constraints

POC_SPEC §12에서 확정(LOCK)된 프로젝트 전역 규칙. 모든 태스크가 암묵적으로 준수한다.

- **브랜드별 코드 0줄.** 브랜드명 분기·하드코딩 금지. 사다리/폴백이 변형을 흡수한다.
- **가격은 항상 코드로만 추출. LLM 금지.** `variants.price` + `compare_at_price`(세일 감지) + shop 통화.
- **LLM 추출 색은 반드시 원본 substring 검증**을 통과해야 채택(날조 차단).
- **컬러 철자 방어:** options name이 `color` 또는 `colour` 둘 다 인식(arch4=British).
- **Shopify 페이지네이션 필수:** `?page=N` 루프로 빈 페이지까지. 미이행 시 조용히 잘림(arch4 실측 500+).
- **결측을 데이터로:** 소스 전부 실패 시 `failure` 필드에 사유 기록, 예외로 파이프라인 중단 금지.
- **8계열 색 매핑·통화 KRW 환산·롤업 집계는 이 플랜 범위 밖**(플랜 #3/#2/#4). 이 플랜은 원색명·native 가격·통화코드까지만.

### 범위 경계 (명시적 축소 — owner 확인됨)

- **rung1(Shopify)만 구현.** 소스 사다리 6몰(guestinresidence·lisayang=USD, extreme=EUR, &daughter·arch4·cashmereinlove=GBP) 커버. `/meta.json`·`/products.json` 4몰 라이브 검증 완료(2026-07-20).
- **rung2(sitemap)·rung3(JSON-LD/`__NEXT_DATA__`)·rung4(crawl4ai 렌더)는 플랜 #1b로 연기.** 이 플랜의 `run_ladder`는 rung 추가가 리스트 append 한 줄이 되도록 설계한다. 비Shopify 브랜드(Quince·Iris·LE17·COS)는 이 플랜에서 `source=None, failure` 기록(정직한 커버리지 갭).

---

## File Structure

- `requirements-dev.txt` — 신규. pytest.
- `datalayer/__init__.py` — 신규. 빈 패키지 마커.
- `datalayer/records.py` — 신규. `ProductRecord`, `BrandExtractionResult` dataclass.
- `datalayer/fields.py` — 신규. 공유 필드 폴백 헬퍼(가격/아이템/색/소재 + substring 검증).
- `datalayer/sources/__init__.py` — 신규. 빈 마커.
- `datalayer/sources/base.py` — 신규. `Source` Protocol.
- `datalayer/sources/shopify.py` — 신규. `ShopifySource` + Shopify 상품→`ProductRecord` 매핑.
- `datalayer/ladder.py` — 신규. `run_ladder` 소스 사다리 러너.
- `datalayer/extract.py` — 신규. `extract_brand`/`extract_all` 기본 배선.
- `tests/datalayer/__init__.py` — 신규.
- `tests/datalayer/test_records.py`, `test_fields.py`, `test_ladder.py`, `test_shopify.py`, `test_extract.py` — 신규.
- `tests/datalayer/fixtures.py` — 신규. Shopify MockTransport 픽스처.

---

## Task 0: 테스트 인프라 + 패키지 스켈레톤

**Files:**
- Create: `requirements-dev.txt`
- Create: `datalayer/__init__.py`
- Create: `datalayer/sources/__init__.py`
- Create: `tests/datalayer/__init__.py`

**Interfaces:**
- Produces: 설치된 pytest, import 가능한 `datalayer` 패키지.

- [ ] **Step 1: dev 의존성 파일 작성**

`requirements-dev.txt`:
```
pytest>=8
```

- [ ] **Step 2: 빈 패키지 마커 생성**

`datalayer/__init__.py`:
```python
"""MVP 데이터 레이어 (POC_SPEC §12). 소스 획득 + 필드 추출."""
```

`datalayer/sources/__init__.py`:
```python
```

`tests/datalayer/__init__.py`:
```python
```

- [ ] **Step 3: pytest 설치**

Run: `.venv/bin/pip install -r requirements-dev.txt`
Expected: `Successfully installed pytest-8.x`

- [ ] **Step 4: 수집 확인**

Run: `.venv/bin/python -m pytest tests/datalayer -q`
Expected: `no tests ran` (수집 에러 없음, 아직 테스트 0개)

- [ ] **Step 5: Commit**

```bash
git add requirements-dev.txt datalayer/__init__.py datalayer/sources/__init__.py tests/datalayer/__init__.py
git commit -m "chore: MVP datalayer 패키지 스켈레톤 + pytest dev dep"
```

---

## Task 1: 정규화 레코드 dataclass

**Files:**
- Create: `datalayer/records.py`
- Test: `tests/datalayer/test_records.py`

**Interfaces:**
- Produces:
  - `ProductRecord(brand:str, url:str, item:str|None, colors_raw:list[str], price_native:float|None, currency:str|None, compare_at_native:float|None, on_sale:bool, materials:list[str], published_at:str|None, source:str)`
  - `BrandExtractionResult(brand:str, source:str|None, products:list[ProductRecord]=[], failure:str|None=None)`

- [ ] **Step 1: 실패 테스트 작성**

`tests/datalayer/test_records.py`:
```python
from datalayer.records import ProductRecord, BrandExtractionResult


def test_product_record_holds_normalized_fields():
    r = ProductRecord(
        brand="arch4", url="https://www.arch4.co.uk/products/x",
        item="Sweater", colors_raw=["Camel"], price_native=240.0,
        currency="GBP", compare_at_native=625.0, on_sale=True,
        materials=["cashmere"], published_at="2026-06-01", source="shopify",
    )
    assert r.on_sale is True
    assert r.colors_raw == ["Camel"]
    assert r.currency == "GBP"


def test_brand_result_defaults_empty_and_no_failure():
    br = BrandExtractionResult(brand="quince", source=None)
    assert br.products == []
    assert br.failure is None
    assert br.source is None
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_records.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'datalayer.records'`

- [ ] **Step 3: 구현**

`datalayer/records.py`:
```python
"""정규화 상품 레코드. POC_SPEC §12.4 브랜드 블록의 입력."""
from dataclasses import dataclass, field


@dataclass
class ProductRecord:
    brand: str
    url: str
    item: str | None                 # product_type (없으면 None)
    colors_raw: list[str]            # 원색명 (8계열 매핑은 플랜 #3)
    price_native: float | None       # shop 통화 기준 금액
    currency: str | None             # ISO 코드 (USD/EUR/GBP)
    compare_at_native: float | None  # 정가 (세일 감지용)
    on_sale: bool
    materials: list[str]             # 소재 키워드
    published_at: str | None         # ISO 날짜 (YYYY-MM-DD)
    source: str                      # 성공한 rung (예 "shopify")


@dataclass
class BrandExtractionResult:
    brand: str
    source: str | None                          # 성공 rung, 전부 실패 시 None
    products: list[ProductRecord] = field(default_factory=list)
    failure: str | None = None                  # 전 rung 실패 시 사유
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_records.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add datalayer/records.py tests/datalayer/test_records.py
git commit -m "feat(datalayer): ProductRecord/BrandExtractionResult 정규화 레코드"
```

---

## Task 2: 가격 필드 추출 (코드 전용, LLM 금지)

**Files:**
- Create: `datalayer/fields.py`
- Test: `tests/datalayer/test_fields.py`

**Interfaces:**
- Produces:
  - `to_float(v) -> float|None`
  - `extract_price(variant:dict) -> tuple[float|None, float|None, bool]` — (price, compare_at, on_sale)

- [ ] **Step 1: 실패 테스트 작성**

`tests/datalayer/test_fields.py`:
```python
from datalayer import fields


def test_to_float_strips_commas_and_handles_none():
    assert fields.to_float("1,250.00") == 1250.0
    assert fields.to_float("240.00") == 240.0
    assert fields.to_float(None) is None
    assert fields.to_float("") is None


def test_extract_price_detects_sale_when_compare_greater():
    # arch4 실측: price=240 compare=625 → 세일
    price, compare, on_sale = fields.extract_price(
        {"price": "240.00", "compare_at_price": "625.00"})
    assert (price, compare, on_sale) == (240.0, 625.0, True)


def test_extract_price_equal_compare_is_not_sale():
    # guestinresidence 실측: 445==445 → 세일 아님
    _, _, on_sale = fields.extract_price(
        {"price": "445.00", "compare_at_price": "445.00"})
    assert on_sale is False


def test_extract_price_none_compare_is_not_sale():
    # extreme 실측: compare=None → 세일 아님
    price, compare, on_sale = fields.extract_price(
        {"price": "650.00", "compare_at_price": None})
    assert (price, compare, on_sale) == (650.0, None, False)
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_fields.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'datalayer.fields'`

- [ ] **Step 3: 구현**

`datalayer/fields.py`:
```python
"""공유 필드 폴백 헬퍼. POC_SPEC §12.2 (구조화→LLM→substring 검증)."""
from typing import Callable

LLMFn = Callable[[str], str]


def to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def extract_price(variant: dict) -> tuple[float | None, float | None, bool]:
    """(price, compare_at, on_sale). 항상 코드, LLM 금지 (§12.2)."""
    price = to_float(variant.get("price"))
    compare = to_float(variant.get("compare_at_price"))
    on_sale = compare is not None and price is not None and compare > price
    return price, compare, on_sale
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_fields.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add datalayer/fields.py tests/datalayer/test_fields.py
git commit -m "feat(datalayer): 가격/세일 추출 (코드 전용, §12.2)"
```

---

## Task 3: 소재 + 아이템 필드 추출

**Files:**
- Modify: `datalayer/fields.py`
- Test: `tests/datalayer/test_fields.py` (테스트 추가)

**Interfaces:**
- Consumes: `LLMFn` (Task 2)
- Produces:
  - `MATERIAL_KEYWORDS: list[str]`
  - `extract_materials(*texts:str) -> list[str]`
  - `extract_item(product_type:str|None, title:str, tags:list[str], llm_fn:LLMFn|None=None) -> str|None`

- [ ] **Step 1: 실패 테스트 추가**

`tests/datalayer/test_fields.py`에 추가:
```python
def test_extract_materials_scans_all_texts_case_insensitive():
    mats = fields.extract_materials("100% Cashmere Sweater", "wool, silk", "")
    assert set(mats) == {"cashmere", "wool", "silk"}


def test_extract_materials_empty_when_no_keyword():
    assert fields.extract_materials("plain top", "") == []


def test_extract_item_prefers_product_type():
    assert fields.extract_item("Sweater", "Cozy Knit", ["knit"]) == "Sweater"


def test_extract_item_none_when_empty_and_no_llm():
    assert fields.extract_item("", "Cozy Knit", ["knit"], llm_fn=None) is None
    assert fields.extract_item(None, "Cozy Knit", ["knit"]) is None


def test_extract_item_llm_fallback_when_product_type_blank():
    calls = []

    def fake_llm(prompt: str) -> str:
        calls.append(prompt)
        return "Cardigan"

    out = fields.extract_item("", "Wool Button Front", ["outerwear"], llm_fn=fake_llm)
    assert out == "Cardigan"
    assert len(calls) == 1


def test_extract_item_llm_unknown_maps_to_none():
    out = fields.extract_item("", "Mystery", [], llm_fn=lambda p: "unknown")
    assert out is None
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_fields.py -v`
Expected: FAIL — `AttributeError: module 'datalayer.fields' has no attribute 'extract_materials'`

- [ ] **Step 3: 구현 추가**

`datalayer/fields.py` 끝에 추가:
```python
MATERIAL_KEYWORDS = [
    "cashmere", "wool", "lambswool", "merino", "mohair", "alpaca",
    "cotton", "silk", "linen", "cashair", "polyester", "nylon",
    "viscose", "leather", "angora",
]


def extract_materials(*texts: str) -> list[str]:
    """tags·title·body_html 등에서 소재 키워드 스캔 (§12.2)."""
    blob = " ".join(t for t in texts if t).lower()
    return [m for m in MATERIAL_KEYWORDS if m in blob]


def extract_item(product_type: str | None, title: str, tags: list[str],
                 llm_fn: LLMFn | None = None) -> str | None:
    """① product_type → ② 비면 LLM(title/tags) 폴백 (§12.2)."""
    if product_type and product_type.strip():
        return product_type.strip()
    if llm_fn is None:
        return None
    prompt = (
        "다음 상품의 아이템 유형을 한 단어~짧은 구로만 답하라 "
        "(예: Sweater, Cardigan, Dress). 모르면 'unknown'.\n"
        f"제목: {title}\n태그: {', '.join(tags)}"
    )
    out = (llm_fn(prompt) or "").strip()
    return None if not out or out.lower() == "unknown" else out
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_fields.py -v`
Expected: PASS (10 passed — Task2 4개 + Task3 6개)

- [ ] **Step 5: Commit**

```bash
git add datalayer/fields.py tests/datalayer/test_fields.py
git commit -m "feat(datalayer): 소재 스캔 + 아이템 추출(LLM 폴백)"
```

---

## Task 4: 색 필드 추출 + substring 검증

**Files:**
- Modify: `datalayer/fields.py`
- Test: `tests/datalayer/test_fields.py` (테스트 추가)

**Interfaces:**
- Consumes: `LLMFn` (Task 2)
- Produces:
  - `pick_structured_colors(options:list[dict]) -> list[str]`
  - `verify_substring(token:str, raw_blob:str) -> bool`
  - `llm_color_fallback(title:str, tags:list[str], raw_blob:str, llm_fn:LLMFn) -> list[str]`
  - `extract_colors(options:list[dict], title:str, tags:list[str], raw_blob:str, llm_fn:LLMFn|None=None) -> list[str]`

- [ ] **Step 1: 실패 테스트 추가**

`tests/datalayer/test_fields.py`에 추가:
```python
def test_pick_structured_colors_handles_both_spellings():
    us = [{"name": "Color", "values": ["Camel", "Grey"]}]
    uk = [{"name": "Colour", "values": ["Navy"]}]
    assert fields.pick_structured_colors(us) == ["Camel", "Grey"]
    assert fields.pick_structured_colors(uk) == ["Navy"]


def test_pick_structured_colors_empty_when_no_color_option():
    assert fields.pick_structured_colors([{"name": "Size", "values": ["S"]}]) == []


def test_verify_substring_case_insensitive():
    assert fields.verify_substring("Camel", "soft CAMEL wool") is True
    assert fields.verify_substring("Emerald", "soft camel wool") is False
    assert fields.verify_substring("", "anything") is False


def test_extract_colors_prefers_structured_no_llm_call():
    called = []
    opts = [{"name": "color", "values": ["Ivory"]}]
    out = fields.extract_colors(opts, "t", [], "raw", llm_fn=lambda p: called.append(p) or "X")
    assert out == ["Ivory"]
    assert called == []  # 구조화 성공 시 LLM 미호출


def test_extract_colors_llm_fallback_keeps_only_verified():
    # LLM이 Camel(원본 존재)·Emerald(원본 없음) 반환 → Camel만 채택
    raw = "Beautiful camel knit cardigan"
    out = fields.extract_colors(
        [], "Camel Cardigan", ["knit"], raw, llm_fn=lambda p: "Camel, Emerald")
    assert out == ["Camel"]


def test_extract_colors_no_structured_no_llm_returns_empty():
    assert fields.extract_colors([], "t", [], "raw", llm_fn=None) == []
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_fields.py -v`
Expected: FAIL — `AttributeError: module 'datalayer.fields' has no attribute 'pick_structured_colors'`

- [ ] **Step 3: 구현 추가**

`datalayer/fields.py` 끝에 추가:
```python
def pick_structured_colors(options: list[dict]) -> list[str]:
    """options 중 name이 color/colour(철자 방어)인 것의 values."""
    for o in options:
        if str(o.get("name", "")).strip().lower() in ("color", "colour"):
            return [str(v).strip() for v in o.get("values", []) if str(v).strip()]
    return []


def verify_substring(token: str, raw_blob: str) -> bool:
    """LLM 추출 색이 원본에 실제 존재하는지 (날조 차단, §12.2)."""
    return bool(token) and token.lower() in raw_blob.lower()


def llm_color_fallback(title: str, tags: list[str], raw_blob: str,
                       llm_fn: LLMFn) -> list[str]:
    prompt = (
        "다음 상품 텍스트에서 색상명만 쉼표로 나열하라. 색이 없으면 빈 줄.\n"
        f"제목: {title}\n태그: {', '.join(tags)}"
    )
    out = llm_fn(prompt) or ""
    cands = [c.strip() for c in out.split(",") if c.strip()]
    return [c for c in cands if verify_substring(c, raw_blob)]


def extract_colors(options: list[dict], title: str, tags: list[str],
                   raw_blob: str, llm_fn: LLMFn | None = None) -> list[str]:
    """① 구조화 options → ② LLM 추출 + substring 검증 (§12.2)."""
    structured = pick_structured_colors(options)
    if structured:
        return structured
    if llm_fn is None:
        return []
    return llm_color_fallback(title, tags, raw_blob, llm_fn)
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_fields.py -v`
Expected: PASS (16 passed)

- [ ] **Step 5: Commit**

```bash
git add datalayer/fields.py tests/datalayer/test_fields.py
git commit -m "feat(datalayer): 색 추출 구조화+LLM폴백+substring 검증(§12.2)"
```

---

## Task 5: 소스 사다리 러너

**Files:**
- Create: `datalayer/sources/base.py`
- Create: `datalayer/ladder.py`
- Test: `tests/datalayer/test_ladder.py`

**Interfaces:**
- Consumes: `ProductRecord`, `BrandExtractionResult` (Task 1)
- Produces:
  - `Source` Protocol: `name:str`, `fetch(brand:str, homepage_url:str, client:httpx.Client) -> list[ProductRecord]|None`
  - `run_ladder(brand:str, homepage_url:str, sources:list[Source], client:httpx.Client) -> BrandExtractionResult`

- [ ] **Step 1: 실패 테스트 작성**

`tests/datalayer/test_ladder.py`:
```python
from datalayer.ladder import run_ladder
from datalayer.records import ProductRecord


def _rec(brand):
    return ProductRecord(brand, "u", "Sweater", [], 1.0, "USD", None,
                         False, [], None, "shopify")


class _NoneSource:
    name = "sitemap"
    def fetch(self, brand, url, client):
        return None


class _OkSource:
    name = "shopify"
    def fetch(self, brand, url, client):
        return [_rec(brand)]


class _BoomSource:
    name = "render"
    def fetch(self, brand, url, client):
        raise RuntimeError("kaboom")


def test_ladder_takes_first_non_none_source():
    res = run_ladder("arch4", "https://x", [_NoneSource(), _OkSource()], client=None)
    assert res.source == "shopify"
    assert len(res.products) == 1
    assert res.failure is None


def test_ladder_all_none_records_failure_not_raise():
    res = run_ladder("quince", "https://x", [_NoneSource()], client=None)
    assert res.source is None
    assert res.products == []
    assert "지원 소스 없음" in res.failure


def test_ladder_captures_source_exception_and_continues():
    res = run_ladder("y", "https://x", [_BoomSource(), _OkSource()], client=None)
    assert res.source == "shopify"  # 예외 rung 건너뛰고 다음 성공


def test_ladder_all_fail_with_exception_records_error():
    res = run_ladder("y", "https://x", [_BoomSource()], client=None)
    assert res.source is None
    assert "render" in res.failure and "kaboom" in res.failure
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_ladder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'datalayer.ladder'`

- [ ] **Step 3: 구현**

`datalayer/sources/base.py`:
```python
"""소스 사다리 rung 인터페이스."""
from typing import Protocol

import httpx

from datalayer.records import ProductRecord


class Source(Protocol):
    name: str

    def fetch(self, brand: str, homepage_url: str,
              client: httpx.Client) -> list[ProductRecord] | None:
        """이 소스로 처리 가능하면 ProductRecord 리스트, 불가하면 None."""
        ...
```

`datalayer/ladder.py`:
```python
"""소스 사다리: 순서대로 시도, 첫 성공 채택 (POC_SPEC §12.1)."""
import httpx

from datalayer.records import BrandExtractionResult
from datalayer.sources.base import Source


def run_ladder(brand: str, homepage_url: str, sources: list[Source],
               client: httpx.Client) -> BrandExtractionResult:
    errors: list[str] = []
    for src in sources:
        try:
            products = src.fetch(brand, homepage_url, client)
        except Exception as e:  # rung 실패는 기록하고 다음 rung 진행
            errors.append(f"{src.name}: {type(e).__name__}: {e}")
            continue
        if products is not None:
            return BrandExtractionResult(brand=brand, source=src.name, products=products)
    fail = "; ".join(errors) if errors else "지원 소스 없음(전 rung None)"
    return BrandExtractionResult(brand=brand, source=None, products=[], failure=fail)
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_ladder.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add datalayer/sources/base.py datalayer/ladder.py tests/datalayer/test_ladder.py
git commit -m "feat(datalayer): 소스 사다리 러너 + Source 인터페이스(§12.1)"
```

---

## Task 6: Shopify 소스 (rung1)

**Files:**
- Create: `datalayer/sources/shopify.py`
- Create: `tests/datalayer/fixtures.py`
- Test: `tests/datalayer/test_shopify.py`

**Interfaces:**
- Consumes: `fields.*` (Task 2-4), `ProductRecord` (Task 1), `LLMFn` (Task 2)
- Produces:
  - `ShopifySource(llm_fn:LLMFn|None=None)` with `name="shopify"`, `fetch(brand, homepage_url, client) -> list[ProductRecord]|None`
  - 모듈 상수 `MAX_PAGES=40`

- [ ] **Step 1: 픽스처 + 실패 테스트 작성**

`tests/datalayer/fixtures.py`:
```python
"""가짜 Shopify 몰 MockTransport. /products.json 페이지네이션 + /meta.json."""
import json

import httpx

_PRODUCTS = [
    {  # 세일 상품, colour(British) 스펠링
        "handle": "camel-cardigan", "title": "Baby Cashmere Cardigan",
        "product_type": "Cardigan", "tags": ["knit", "cashmere"],
        "body_html": "<p>100% Cashmere</p>", "published_at": "2026-06-15T00:00:00Z",
        "options": [{"name": "Colour", "values": ["Camel", "Grey"]}],
        "variants": [{"price": "240.00", "compare_at_price": "625.00"}],
    },
    {  # product_type 비어있음 → 아이템 LLM 폴백 대상, color 옵션 없음
        "handle": "wool-scarf", "title": "Merino Scarf",
        "product_type": "", "tags": ["accessory"],
        "body_html": "<p>Merino wool, navy</p>", "published_at": "2026-05-01T00:00:00Z",
        "options": [{"name": "Title", "values": ["Default"]}],
        "variants": [{"price": "95.00", "compare_at_price": None}],
    },
]


def shopify_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/meta.json":
        return httpx.Response(200, json={"currency": "GBP"})
    if path == "/products.json":
        page = int(request.url.params.get("page", "1"))
        batch = _PRODUCTS if page == 1 else []
        return httpx.Response(200, json={"products": batch})
    return httpx.Response(404)


def shopify_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(shopify_handler),
                        base_url="https://shop.test")


def non_shopify_client() -> httpx.Client:
    def handler(request):
        return httpx.Response(404, text="Not Found")
    return httpx.Client(transport=httpx.MockTransport(handler))
```

`tests/datalayer/test_shopify.py`:
```python
from datalayer.sources.shopify import ShopifySource
from tests.datalayer.fixtures import shopify_client, non_shopify_client


def test_shopify_fetch_maps_products():
    with shopify_client() as c:
        recs = ShopifySource().fetch("arch4", "https://shop.test/", c)
    assert recs is not None and len(recs) == 2
    cardigan = recs[0]
    assert cardigan.item == "Cardigan"
    assert cardigan.colors_raw == ["Camel", "Grey"]      # Colour 스펠링 인식
    assert (cardigan.price_native, cardigan.compare_at_native) == (240.0, 625.0)
    assert cardigan.on_sale is True
    assert cardigan.currency == "GBP"                     # meta.json
    assert "cashmere" in cardigan.materials
    assert cardigan.published_at == "2026-06-15"
    assert cardigan.url == "https://shop.test/products/camel-cardigan"
    assert cardigan.source == "shopify"


def test_shopify_item_llm_fallback_when_product_type_blank():
    with shopify_client() as c:
        recs = ShopifySource(llm_fn=lambda p: "Scarf").fetch("b", "https://shop.test/", c)
    scarf = recs[1]
    assert scarf.item == "Scarf"                          # product_type 빈값→LLM


def test_shopify_color_llm_fallback_verified_against_body():
    # scarf는 color 옵션 없음. LLM이 navy(body에 존재)·pink(없음) → navy만 채택
    with shopify_client() as c:
        recs = ShopifySource(llm_fn=lambda p: "navy, pink").fetch("b", "https://shop.test/", c)
    scarf = recs[1]
    assert scarf.colors_raw == ["navy"]


def test_shopify_returns_none_for_non_shopify():
    with non_shopify_client() as c:
        assert ShopifySource().fetch("cos", "https://shop.test/", c) is None
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_shopify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'datalayer.sources.shopify'`

- [ ] **Step 3: 구현**

`datalayer/sources/shopify.py`:
```python
"""rung1 — Shopify /products.json. POC_SPEC §12.1."""
from urllib.parse import urlparse

import httpx

from datalayer import fields
from datalayer.fields import LLMFn
from datalayer.records import ProductRecord

MAX_PAGES = 40  # 250*40=10000 상품 안전상한 (초과 시 조용히 잘림 방지용 캡)


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _shop_currency(origin: str, client: httpx.Client) -> str | None:
    try:
        r = client.get(f"{origin}/meta.json")
        if r.status_code == 200:
            return r.json().get("currency")
    except (httpx.HTTPError, ValueError):
        pass
    return None


def _fetch_all(origin: str, client: httpx.Client) -> list[dict]:
    products: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        r = client.get(f"{origin}/products.json", params={"limit": 250, "page": page})
        r.raise_for_status()
        batch = r.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
    return products


def _normalize_tags(tags) -> list[str]:
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    return [str(t).strip() for t in (tags or []) if str(t).strip()]


def _map(p: dict, brand: str, currency: str | None, origin: str,
         llm_fn: LLMFn | None) -> ProductRecord:
    variants = p.get("variants") or [{}]
    price, compare, on_sale = fields.extract_price(variants[0])
    title = p.get("title", "") or ""
    tags = _normalize_tags(p.get("tags"))
    body = p.get("body_html", "") or ""
    options = p.get("options") or []
    raw_blob = " ".join([title, " ".join(tags), body,
                         " ".join(str(o) for o in options)])
    return ProductRecord(
        brand=brand,
        url=f"{origin}/products/{p.get('handle', '')}",
        item=fields.extract_item(p.get("product_type"), title, tags, llm_fn),
        colors_raw=fields.extract_colors(options, title, tags, raw_blob, llm_fn),
        price_native=price,
        currency=currency,
        compare_at_native=compare,
        on_sale=on_sale,
        materials=fields.extract_materials(title, " ".join(tags), body),
        published_at=(p.get("published_at") or "")[:10] or None,
        source="shopify",
    )


class ShopifySource:
    name = "shopify"

    def __init__(self, llm_fn: LLMFn | None = None):
        self.llm_fn = llm_fn

    def fetch(self, brand: str, homepage_url: str,
              client: httpx.Client) -> list[ProductRecord] | None:
        origin = _origin(homepage_url)
        try:  # 프로브: Shopify 여부 판정 (limit=1)
            r = client.get(f"{origin}/products.json", params={"limit": 1, "page": 1})
        except httpx.HTTPError:
            return None
        if r.status_code != 200:
            return None
        try:
            data = r.json()
        except ValueError:
            return None
        if "products" not in data:
            return None
        currency = _shop_currency(origin, client)
        raw = _fetch_all(origin, client)
        return [_map(p, brand, currency, origin, self.llm_fn) for p in raw]
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_shopify.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add datalayer/sources/shopify.py tests/datalayer/fixtures.py tests/datalayer/test_shopify.py
git commit -m "feat(datalayer): Shopify 소스 rung1 (페이지네이션+통화+매핑)"
```

---

## Task 7: 배선 (extract_brand / extract_all) + 통합 테스트

**Files:**
- Create: `datalayer/extract.py`
- Test: `tests/datalayer/test_extract.py`

**Interfaces:**
- Consumes: `run_ladder` (Task 5), `ShopifySource` (Task 6), `BrandExtractionResult` (Task 1)
- Produces:
  - `default_sources(llm_fn:LLMFn|None=None) -> list[Source]`
  - `extract_brand(brand:str, homepage_url:str, *, llm_fn=None, client=None) -> BrandExtractionResult`
  - `extract_all(brands, *, llm_fn=None) -> list[BrandExtractionResult]` — `brands`는 `.name`/`.url`/`.auto_collect` 속성 보유 객체 iterable

- [ ] **Step 1: 실패 테스트 작성**

`tests/datalayer/test_extract.py`:
```python
from datalayer import extract
from tests.datalayer.fixtures import shopify_client, non_shopify_client


def test_extract_brand_via_shopify():
    with shopify_client() as c:
        res = extract.extract_brand("arch4", "https://shop.test/", client=c)
    assert res.source == "shopify"
    assert len(res.products) == 2
    assert res.failure is None


def test_extract_brand_non_shopify_records_failure():
    with non_shopify_client() as c:
        res = extract.extract_brand("cos", "https://shop.test/", client=c)
    assert res.source is None
    assert res.products == []
    assert res.failure  # 커버리지 갭 기록


def test_default_sources_only_shopify_for_now():
    names = [s.name for s in extract.default_sources()]
    assert names == ["shopify"]  # rung2-4는 플랜 #1b


def test_extract_all_skips_auto_collect_false():
    class B:
        def __init__(self, name, url, auto):
            self.name, self.url, self.auto_collect = name, url, auto

    brands = [B("a", "https://shop.test/", True), B("skip", "https://shop.test/", False)]
    with shopify_client() as c:
        results = extract.extract_all(brands, client=c)
    assert len(results) == 1
    assert results[0].brand == "a"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'datalayer.extract'`

- [ ] **Step 3: 구현**

`datalayer/extract.py`:
```python
"""소스 사다리 기본 배선. POC_SPEC §12.1/§12.2."""
import httpx

from datalayer.fields import LLMFn
from datalayer.ladder import run_ladder
from datalayer.records import BrandExtractionResult
from datalayer.sources.base import Source
from datalayer.sources.shopify import ShopifySource

DEFAULT_TIMEOUT = 30


def default_sources(llm_fn: LLMFn | None = None) -> list[Source]:
    """소스 사다리 rung 순서. 현재 rung1(Shopify)만 — rung2-4는 플랜 #1b."""
    return [ShopifySource(llm_fn=llm_fn)]


def _client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    return httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True), True


def extract_brand(brand: str, homepage_url: str, *,
                  llm_fn: LLMFn | None = None,
                  client: httpx.Client | None = None) -> BrandExtractionResult:
    c, own = _client(client)
    try:
        return run_ladder(brand, homepage_url, default_sources(llm_fn), c)
    finally:
        if own:
            c.close()


def extract_all(brands, *, llm_fn: LLMFn | None = None,
                client: httpx.Client | None = None) -> list[BrandExtractionResult]:
    """auto_collect=True 브랜드만 순회. 단일 client 재사용."""
    c, own = _client(client)
    try:
        results = []
        for b in brands:
            if not getattr(b, "auto_collect", True):
                continue
            results.append(extract_brand(b.name, b.url, llm_fn=llm_fn, client=c))
        return results
    finally:
        if own:
            c.close()
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/datalayer/test_extract.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 전체 스위트 확인**

Run: `.venv/bin/python -m pytest tests/datalayer -v`
Expected: PASS (30 passed — records 2, fields 16, ladder 4, shopify 4, extract 4)

- [ ] **Step 6: Commit**

```bash
git add datalayer/extract.py tests/datalayer/test_extract.py
git commit -m "feat(datalayer): extract_brand/extract_all 배선 + 통합 테스트"
```

---

## Task 8: 라이브 스모크 확인 (수동, 선택)

**Files:**
- Create: `datalayer/smoke.py` (수동 실행용, 커밋)

**Interfaces:**
- Consumes: `extract_brand` (Task 7), `poc.config.BRANDS`

- [ ] **Step 1: 스모크 스크립트 작성**

`datalayer/smoke.py`:
```python
"""라이브 스모크: python -m datalayer.smoke [브랜드명부분]
실제 몰에 붙어 추출 결과 요약 출력. 테스트 아님(네트워크 의존)."""
import sys

from poc import config
from datalayer.extract import extract_brand


def main() -> int:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    for b in config.BRANDS:
        if not b.auto_collect or (needle and needle not in b.name.lower()):
            continue
        res = extract_brand(b.name, b.url)
        if res.source is None:
            print(f"{b.name:20} source=None  FAIL: {res.failure[:80]}")
            continue
        n = len(res.products)
        with_price = sum(1 for p in res.products if p.price_native is not None)
        with_color = sum(1 for p in res.products if p.colors_raw)
        cur = res.products[0].currency if res.products else "?"
        print(f"{b.name:20} source={res.source} n={n} cur={cur} "
              f"price={with_price}/{n} color={with_color}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Shopify 몰 라이브 실행**

Run: `.venv/bin/python -m datalayer.smoke arch4`
Expected: `arch4  source=shopify n=<500+> cur=GBP price=<n>/<n> color=<대다수>/<n>`
(페이지네이션 동작 시 n이 250 초과. 250에서 멈추면 페이지네이션 버그.)

- [ ] **Step 3: 비Shopify 몰 실패 기록 확인**

Run: `.venv/bin/python -m datalayer.smoke quince`
Expected: `quince  source=None  FAIL: ...` (rung2-4 미구현 → 정직한 갭. 플랜 #1b 대상)

- [ ] **Step 4: Commit**

```bash
git add datalayer/smoke.py
git commit -m "chore(datalayer): 라이브 스모크 스크립트"
```

---

## Self-Review

**1. Spec coverage (§12.1/§12.2):**
- §12.1 소스 사다리 "순서대로·첫 성공" → Task 5 `run_ladder`. ✓
- §12.1 rung1 Shopify /products.json **페이지네이션 필수** → Task 6 `_fetch_all` 루프 + Task 8 스모크로 250 초과 확인. ✓
- §12.1 shop 통화 → Task 6 `_shop_currency`(/meta.json). ✓
- §12.1 rung2-4 → **명시적으로 플랜 #1b 연기**(범위 경계 절 + `default_sources` 주석 + Task8 갭 확인). ✓ (의도적 미구현, 은폐 아님)
- §12.2 가격 항상 코드 → Task 2 `extract_price`, LLM 미사용. ✓
- §12.2 아이템 product_type→LLM → Task 3 `extract_item`. ✓
- §12.2 색 구조화→LLM→substring 검증 → Task 4 `extract_colors`+`verify_substring`. ✓
- §12.2 color/colour 철자 방어 → Task 4 `pick_structured_colors` + Task 6 픽스처(Colour). ✓
- §12.2 소재 tags·body_html → Task 3 `extract_materials`. ✓
- §12.2 신상 published_at → Task 6 `_map` published_at[:10]. ✓
- Global "결측을 데이터로" → Task 5 `failure` 필드, 예외 미전파. ✓

**연기 확인:** 통화 KRW 환산(§12.3 통화)=플랜 #2, 색 8계열 매핑(§12.3 컬러)=플랜 #3, 롤업(§12.4)=플랜 #4, NAVER(§12.5)=플랜 #5. 이 플랜은 native 가격·원색명까지만 — 경계 명확.

**2. Placeholder scan:** TBD/TODO/"적절히 처리" 없음. 모든 코드 스텝에 완전 코드. ✓

**3. Type consistency:** `LLMFn`(fields.py 정의)를 extract_item/extract_colors/ShopifySource/default_sources 전부 동일 시그니처 사용. `ProductRecord` 필드명이 Task1 정의와 Task6 `_map` 생성이 일치(brand,url,item,colors_raw,price_native,currency,compare_at_native,on_sale,materials,published_at,source). `run_ladder` 반환 `BrandExtractionResult`가 Task7 소비와 일치. ✓
