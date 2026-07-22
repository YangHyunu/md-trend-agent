"""rung1 — Shopify /products.json. POC_SPEC §12.1."""
from urllib.parse import urlparse

import httpx

from datalayer import fields
from datalayer.fields import LLMFn
from datalayer.records import (
    ProductRecord, Variant, canonical_url, derive_variant_metrics,
)

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


def _build_variants(raw_variants: list[dict], handle: str) -> list[Variant]:
    """모든 variant 보존(§10.1). id가 없으면 handle+index로 안정 대체."""
    out: list[Variant] = []
    for i, rv in enumerate(raw_variants):
        price, compare, _ = fields.extract_price(rv)
        vid = rv.get("id")
        variant_id = str(vid) if vid not in (None, "") else f"{handle}-{i}"
        out.append(Variant(
            variant_id=variant_id,
            title=rv.get("title") or None,
            price_native=price,
            compare_at_native=compare,
            available=rv.get("available") if isinstance(rv.get("available"), bool) else None,
        ))
    return out


def _map(p: dict, brand: str, currency: str | None, origin: str,
         llm_fn: LLMFn | None) -> ProductRecord:
    handle = p.get("handle", "") or ""
    variants = _build_variants(p.get("variants") or [], handle)
    metrics = derive_variant_metrics(variants)
    title = p.get("title", "") or ""
    tags = _normalize_tags(p.get("tags"))
    body = p.get("body_html", "") or ""
    options = p.get("options") or []
    raw_blob = " ".join([title, " ".join(tags), body,
                         " ".join(str(o) for o in options)])
    colors_raw = fields.extract_colors(options, title, tags, raw_blob,
                                       handle=handle, llm_fn=llm_fn)
    families: list[str] = []
    for c in colors_raw:
        fam = fields.map_color_family(c)
        if fam and fam not in families:
            families.append(fam)
    # 대표 variant = 최소가 variant (없으면 첫 variant). 하위호환 price_native/compare용.
    priced = [v for v in variants if v.price_native is not None]
    rep = min(priced, key=lambda v: v.price_native) if priced else (variants[0] if variants else None)
    url = f"{origin}/products/{handle}"
    rec = ProductRecord(
        brand=brand,
        url=url,
        item=fields.extract_item(p.get("product_type"), title),
        colors_raw=colors_raw,
        colors_family=families,
        price_native=metrics["price_min_native"],
        currency=currency,
        compare_at_native=rep.compare_at_native if rep else None,
        on_sale=metrics["any_variant_on_sale"],
        materials=fields.extract_materials(title, " ".join(tags), body),
        published_at=(p.get("published_at") or "")[:10] or None,
        source="shopify",
        silhouettes=fields.extract_silhouettes(title, tags, body),
        image_url=((p.get("images") or [{}])[0].get("src") or None),
        canonical_url=canonical_url(url),
        variants=variants,
        price_min_native=metrics["price_min_native"],
        price_max_native=metrics["price_max_native"],
        sale_variant_ratio=metrics["sale_variant_ratio"],
        any_available=metrics["any_available"],
        all_sold_out=metrics["all_sold_out"],
    )
    rec.validate()
    return rec


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
