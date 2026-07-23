"""Breuninger — 브랜드 리스팅 JSON-LD ItemList 파싱 (SPEC_V2 §10.2 rung4 JSON-LD).

Iris von Arnim 등 브랜드 리스팅(`/de/marken/<brand>/`)은 `application/ld+json`
ItemList로 상품을 노출한다. itemListElement의 @type=Product에서 name·offers·url·image를
읽는다. JSON-LD ItemList엔 brand·color·variant·availability가 없어(정직 갭) brand는
인자값, color/variant는 비우고 단일 variant available=None으로 둔다. url은 상대라 origin을
붙인다. 첫 페이지만(페이지네이션 미구현) — 더 풍부한 전량 수집은 공식몰 Shopware
sitemap(1,074 knit PDP) 경로로 확장 가능.
"""
import json
import re
from urllib.parse import urlparse

import httpx

from datalayer import fields
from datalayer.records import (
    ProductRecord, Variant, canonical_url, derive_variant_metrics,
)

_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S)


def _item_list(html: str) -> list[dict]:
    """ld+json 블록 중 ItemList의 Product 요소들을 반환.

    라이브 페이지는 한 블록이 [WebPage, BreadcrumbList, ItemList] 배열 형태라
    dict/list 양쪽을 훑어 @type=ItemList를 찾는다.
    """
    for m in _LD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for obj in (data if isinstance(data, list) else [data]):
            if isinstance(obj, dict) and obj.get("@type") == "ItemList":
                out = []
                for el in obj.get("itemListElement", []):
                    prod = el.get("item", el)
                    if prod.get("@type") == "Product":
                        out.append(prod)
                if out:
                    return out
    return []


def _offer(prod: dict) -> dict:
    off = prod.get("offers")
    if isinstance(off, list):
        return off[0] if off else {}
    return off or {}


def _map(prod: dict, brand: str, origin: str) -> ProductRecord:
    name = prod.get("name", "") or ""
    off = _offer(prod)
    price = off.get("price")
    price_native = float(price) if price is not None else None
    # schema.org availability가 있으면 InStock 여부로, 없으면 unknown(None)
    avail_raw = off.get("availability")
    available = ("InStock" in avail_raw) if isinstance(avail_raw, str) else None
    variant = Variant(
        variant_id=(prod.get("url") or name),
        title=None,
        price_native=price_native,
        compare_at_native=None,
        available=available,
    )
    metrics = derive_variant_metrics([variant])
    rel = prod.get("url") or ""
    url = rel if rel.startswith("http") else f"{origin}{rel}"
    image = prod.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    rec = ProductRecord(
        brand=brand,
        url=url,
        item=fields.match_item(name),
        colors_raw=[],
        colors_family=[],
        price_native=price_native,
        currency=off.get("priceCurrency") if price_native is not None else None,
        compare_at_native=None,
        on_sale=metrics["any_variant_on_sale"],
        materials=fields.extract_materials(name),
        published_at=None,
        source="breuninger",
        silhouettes=fields.extract_silhouettes(name, [], ""),
        image_url=image,
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


class BreuningerSource:
    name = "breuninger"

    def fetch(self, brand: str, homepage_url: str,
              client: httpx.Client) -> list[ProductRecord] | None:
        p = urlparse(homepage_url)
        origin = f"{p.scheme}://{p.netloc}"
        try:
            r = client.get(homepage_url)
        except httpx.HTTPError:
            return None
        if r.status_code != 200:
            return None
        products = _item_list(r.text)
        if not products:
            return None
        return [_map(x, brand, origin) for x in products]
