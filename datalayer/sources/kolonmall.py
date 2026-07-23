"""코오롱몰 — Apollo SSRDataTransport 파싱 (SPEC_V2 §10.2 rung5 hydration data).

코오롱몰은 Next.js App Router(RSC)지만 상품 데이터는 `__next_f` flight가 아니라
`window[Symbol.for("ApolloSSRDataTransport")]` 스크립트의 plain JSON에 있다.
`__typename=products` 컨테이너의 `results[]`/`page`를 파싱한다. 문서에는 추천 블록·
Apollo replay로 동일 키가 여러 번 나오므로 results+page를 가진 최대 컨테이너를 채택한다.

리스트뷰는 색상 단위(색상별 code) — style 묶음/사이즈 variant는 상세페이지 몫이라
카드당 단일 variant로 매핑한다. `wishPrice`는 discountRate=0이면 price와 같은
마케팅 표기라 compare_at으로 쓰지 않는다(가짜 세일가 방지). KRW 고정.
robots는 `/api/rest/`·`/graphql`을 Disallow하므로 내부 API 대신 공개 브랜드 페이지 HTML만 쓴다.
페이지당 수집 수 < page.totalCount면 로그로 남긴다(silent cap 금지).
"""
import json
import logging
import re

import httpx

from datalayer import fields
from datalayer.records import (
    ProductRecord, Variant, canonical_url, derive_variant_metrics,
)

logger = logging.getLogger(__name__)

_CURRENCY = "KRW"
_PRODUCTS_RE = re.compile(r'"products"\s*:\s*\{')


def _match_object(s: str, start: int) -> str | None:
    """s[start]='{' 부터 균형 잡힌 JSON object 슬라이스 반환 (문자열/이스케이프 인지)."""
    depth = 0
    instr = False
    esc = False
    for j in range(start, len(s)):
        c = s[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:j + 1]
    return None


def _products_container(html: str) -> dict | None:
    """results+page를 가진 __typename=products 컨테이너 중 최대(=전체 페이지)를 채택.

    첫 매치를 쓰면 추천 블록(bxRecommendProductsByBrand)에 걸린다 — price 스키마가 다르다.
    """
    best: dict | None = None
    for m in _PRODUCTS_RE.finditer(html):
        blob = _match_object(html, m.end() - 1)
        if blob is None:
            continue
        try:
            obj = json.loads(blob)
        except ValueError:
            continue
        if obj.get("__typename") == "products" and obj.get("results") and obj.get("page"):
            if best is None or len(obj["results"]) > len(best["results"]):
                best = obj
    return best


def _price(price: dict) -> tuple[float | None, float | None, bool]:
    """(price_native, compare_at, on_sale). wishPrice는 할인일 때만 compare_at."""
    p = price.get("price")
    price_native = float(p) if p is not None else None
    disc = price.get("discountRate") or 0
    on_sale = disc > 0
    wish = price.get("wishPrice")
    compare = float(wish) if (on_sale and wish is not None) else None
    return price_native, compare, on_sale


def _map(r: dict, brand: str, homepage_url: str) -> ProductRecord:
    code = r.get("code") or ""
    name = r.get("name", "") or ""
    color = r.get("color")
    price_native, compare, on_sale = _price(r.get("price") or {})
    currency = (r.get("price") or {}).get("currencyIso") or _CURRENCY
    available = r.get("soldOutYn") != "Y"
    variant = Variant(
        variant_id=code,
        title=color,
        price_native=price_native,
        compare_at_native=compare,
        available=available,
    )
    metrics = derive_variant_metrics([variant])
    colors_raw = [color] if color else []
    families: list[str] = []
    for c in colors_raw:
        fam = fields.map_color_family(c)
        if fam and fam not in families:
            families.append(fam)
    url = f"{homepage_url.rstrip('/')}/Product/{code}"
    rec = ProductRecord(
        brand=brand,
        url=url,
        item=fields.match_item(name),
        colors_raw=colors_raw,
        colors_family=families,
        price_native=price_native,
        currency=currency if price_native is not None else None,
        compare_at_native=compare,
        on_sale=on_sale,
        materials=fields.extract_materials(name),
        published_at=None,
        source="kolonmall",
        silhouettes=fields.extract_silhouettes(name, [], ""),
        image_url=r.get("representationImage"),
        canonical_url=canonical_url(url),
        variants=[variant],
        price_min_native=metrics["price_min_native"],
        price_max_native=metrics["price_max_native"],
        sale_variant_ratio=metrics["sale_variant_ratio"],
        any_available=metrics["any_available"],
        all_sold_out=metrics["all_sold_out"],
    )
    rec.validate()
    return rec


class KolonmallSource:
    name = "kolonmall"

    def fetch(self, brand: str, homepage_url: str,
              client: httpx.Client) -> list[ProductRecord] | None:
        try:
            r = client.get(homepage_url)
        except httpx.HTTPError:
            return None
        if r.status_code != 200:
            return None
        container = _products_container(r.text)
        if container is None:
            return None
        results = container["results"]
        total = (container.get("page") or {}).get("totalCount")
        if total is not None and total > len(results):
            logger.warning("kolonmall %s: %d/%d개만 수집 (페이지네이션 미구현)",
                           brand, len(results), total)
        return [_map(x, brand, homepage_url) for x in results]
