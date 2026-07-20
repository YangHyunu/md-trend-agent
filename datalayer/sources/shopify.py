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
