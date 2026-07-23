"""Quince — CLP __NEXT_DATA__ hydration 파싱 (SPEC_V2 §9.1 "Next.js hydration").

공개 SSR 컬렉션 페이지의 PRODUCT_LIST 위젯을 파싱한다. cardVariant는 색상 단위
(사이즈는 사이트가 색상으로 묶음). Quince는 상시가 모델이라 세일 신호가 없고,
`traditionalRetailPrice`는 마케팅 비교가라 compare_at으로 쓰지 않는다.
페이지당 30개 SSR 한계는 pagination.total 대비 수집 수를 로그로 남긴다(silent cap 금지).
"""
import json
import logging
import re
from urllib.parse import urlparse

import httpx

from datalayer import fields
from datalayer.records import (
    ProductRecord, Variant, canonical_url, derive_variant_metrics,
)

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)

# US 스토어프론트(en-us) 고정. 다른 locale 지원 시 registry에서 주입.
_CURRENCY = "USD"
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


def _next_data(html: str) -> dict | None:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def _product_items(data: dict) -> tuple[list[dict], dict]:
    """PRODUCT_LIST children의 productItem들과 pagination을 꺼낸다."""
    try:
        pdj = data["props"]["pageProps"]["pageData"]["context"]["pageDataJson"]
        widgets = pdj["widgets"]
    except (KeyError, TypeError):
        return [], {}
    for w in widgets:
        if w.get("type") == "PRODUCT_LIST":
            items = [ch["data"]["productItem"] for ch in w.get("children", [])
                     if ch.get("data", {}).get("productItem")]
            return items, w.get("pagination") or {}
    return [], {}


def _build_variants(card_variants: list[dict]) -> list[Variant]:
    out: list[Variant] = []
    for cv in card_variants:
        color = (cv.get("displayConfig") or {}).get("value")
        price = (cv.get("price") or {}).get("salePrice")
        tags = {t.get("value") for t in cv.get("tags") or []}
        out.append(Variant(
            variant_id=str(cv.get("variantId")),
            title=color,
            price_native=float(price) if price is not None else None,
            compare_at_native=None,
            available="Sold Out" not in tags,
        ))
    return out


def _map(pi: dict, brand: str, origin: str) -> ProductRecord:
    cls = pi.get("classification") or {}
    title = pi.get("title", "") or ""
    variants = _build_variants(pi.get("cardVariants") or [])
    metrics = derive_variant_metrics(variants)
    colors_raw = [v.title for v in variants if v.title]
    families: list[str] = []
    for c in colors_raw:
        fam = fields.map_color_family(c)
        if fam and fam not in families:
            families.append(fam)
    item = (fields.match_item(cls.get("class"))
            or fields.match_item(cls.get("department"))
            or fields.match_item(title))
    cls_blob = " ".join(str(cls.get(k) or "") for k in ("division", "department",
                                                        "subdepartment", "class"))
    url = f"{origin}/{pi.get('slug', '').lstrip('/')}"
    image = None
    for cv in pi.get("cardVariants") or []:
        imgs = cv.get("images") or []
        if imgs and imgs[0].get("url"):
            image = imgs[0]["url"]
            if image.startswith("//"):
                image = f"https:{image}"
            break
    rec = ProductRecord(
        brand=brand,
        url=url,
        item=item,
        colors_raw=colors_raw,
        colors_family=families,
        price_native=metrics["price_min_native"],
        currency=_CURRENCY if metrics["price_min_native"] is not None else None,
        compare_at_native=None,
        on_sale=metrics["any_variant_on_sale"],
        materials=fields.extract_materials(title, cls_blob),
        published_at=None,
        source="quince_next",
        silhouettes=fields.extract_silhouettes(title, [], ""),
        image_url=image,
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


class QuinceSource:
    name = "quince_next"

    def __init__(self, collection_paths: list[str] | None = None):
        self.collection_paths = collection_paths or _DEFAULT_PATHS

    def fetch(self, brand: str, homepage_url: str,
              client: httpx.Client) -> list[ProductRecord] | None:
        p = urlparse(homepage_url)
        origin = f"{p.scheme}://{p.netloc}"
        records: dict[str, ProductRecord] = {}
        parsed_any = False
        for path in self.collection_paths:
            try:
                r = client.get(f"{origin}/{path}")
            except httpx.HTTPError:
                continue
            if r.status_code != 200:
                continue
            data = _next_data(r.text)
            if data is None:
                continue
            items, pagination = _product_items(data)
            if not items:
                continue
            parsed_any = True
            total = pagination.get("total")
            if total is not None and total > len(items):
                logger.warning("quince %s: SSR %d/%d개만 수집 (페이지네이션 미지원)",
                               path, len(items), total)
            for pi in items:
                pid = str(pi.get("productId") or pi.get("id"))
                if pid not in records:
                    records[pid] = _map(pi, brand, origin)
        if not parsed_any:
            return None
        return list(records.values())
