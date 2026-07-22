"""정규화 상품 레코드. SPEC_V2 §8.4 variant 계약(실용 최소).

전체 Pydantic 마이그레이션(§8)은 §8 전 계약을 함께 옮기는 Phase 0A 작업으로 미룬다.
여기서는 datalayer 나머지와 일관되게 dataclass를 유지하고, variant 계약 불변조건은
`validate()`로 검사한다(adapter가 record를 만든 뒤 호출).
"""
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA_VERSION = "2.0"

# canonical URL에서 제거할 tracking query 접두/키 (§8.4).
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_"}


def canonical_url(url: str) -> str:
    """fragment와 tracking query를 제거한 HTTPS-선호 canonical URL(§8.4).

    source별 allowlist query 없이 보수적으로 tracking만 제거한다. 그 외 query는 보존.
    """
    parts = urlsplit(url.strip())
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not (k.lower().startswith(_TRACKING_PREFIXES) or k.lower() in _TRACKING_KEYS)
    ]
    return urlunsplit((
        parts.scheme, parts.netloc, parts.path, urlencode(kept), "",  # fragment 제거
    ))


@dataclass
class Variant:
    """상품 옵션 단위. 첫 variant만 상품 전체 가격/세일로 쓰지 않는다(§8.4)."""
    variant_id: str
    title: str | None
    price_native: float | None
    compare_at_native: float | None
    available: bool | None


def derive_variant_metrics(variants: list[Variant]) -> dict:
    """variant 목록에서 min/max가·세일·재고 집계를 계산한다(§8.4 불변조건 그대로).

    - price_min/max: price_native가 있는 variant만
    - sale: compare_at > price 인 variant만 세일. ratio = 세일 variant / 전체
    - any_available = any(available is True)
    - all_sold_out = variant가 있고 모두 명시적으로 False일 때만 True
    """
    prices = [v.price_native for v in variants if v.price_native is not None]
    price_min = min(prices) if prices else None
    price_max = max(prices) if prices else None

    on_sale_variants = [
        v for v in variants
        if v.price_native is not None and v.compare_at_native is not None
        and v.compare_at_native > v.price_native
    ]
    any_on_sale = len(on_sale_variants) > 0
    sale_ratio = round(len(on_sale_variants) / len(variants), 4) if variants else None

    avails = [v.available for v in variants]
    any_available: bool | None
    all_sold_out: bool | None
    if not avails or all(a is None for a in avails):
        any_available = None
        all_sold_out = None
    else:
        any_available = any(a is True for a in avails)
        all_sold_out = all(a is False for a in avails)

    return {
        "price_min_native": price_min,
        "price_max_native": price_max,
        "any_variant_on_sale": any_on_sale,
        "sale_variant_ratio": sale_ratio,
        "any_available": any_available,
        "all_sold_out": all_sold_out,
    }


@dataclass
class ProductRecord:
    brand: str
    url: str
    item: str | None                 # product_type (없으면 None)
    colors_raw: list[str]            # 원색명 (근거 보존)
    price_native: float | None       # 대표가 = variant 최소가 (하위호환)
    currency: str | None             # ISO 코드 (USD/EUR/GBP)
    compare_at_native: float | None  # 대표 정가 (세일 감지용)
    on_sale: bool                    # = any_variant_on_sale (하위호환)
    materials: list[str]             # 소재 키워드
    published_at: str | None         # ISO 날짜 (YYYY-MM-DD)
    source: str                      # 성공한 rung (예 "shopify")
    silhouettes: list[str] = field(default_factory=list)  # 핏/볼륨 (MDA-4 rung1)
    colors_family: list[str] = field(default_factory=list)  # 8계열 매핑 (MDA-8)
    image_url: str | None = None     # 대표 이미지 (피드 첫 이미지 — 보고서 썸네일용)
    # --- SPEC_V2 §8.4 variant 계약 (실용 최소) ---
    canonical_url: str | None = None
    variants: list[Variant] = field(default_factory=list)
    price_min_native: float | None = None
    price_max_native: float | None = None
    sale_variant_ratio: float | None = None
    any_available: bool | None = None
    all_sold_out: bool | None = None
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        """§8.4 variant 계약 불변조건. 위반 시 ValueError."""
        seen: set[str] = set()
        for v in self.variants:
            if not isinstance(v.variant_id, str) or not v.variant_id:
                raise ValueError(f"variant_id는 비어있지 않은 문자열이어야 함: {v!r}")
            if v.variant_id in seen:
                raise ValueError(f"variant_id 중복: {v.variant_id!r}")
            seen.add(v.variant_id)
            if v.price_native is not None:
                if not (v.price_native == v.price_native and v.price_native >= 0):
                    raise ValueError(f"variant 가격은 finite·0 이상: {v.price_native!r}")

        if (self.price_min_native is not None and self.price_max_native is not None
                and self.price_min_native > self.price_max_native):
            raise ValueError(
                f"price_min({self.price_min_native}) > price_max({self.price_max_native})")

        # native amount와 currency는 all-or-none
        if self.price_min_native is not None and not self.currency:
            raise ValueError("native 가격이 있으면 currency가 있어야 함")

        if self.sale_variant_ratio is not None and not (0 <= self.sale_variant_ratio <= 1):
            raise ValueError(f"sale_variant_ratio는 0~1: {self.sale_variant_ratio!r}")


@dataclass
class BrandExtractionResult:
    brand: str
    source: str | None                          # 성공 rung, 전부 실패 시 None
    products: list[ProductRecord] = field(default_factory=list)
    failure: str | None = None                  # 전 rung 실패 시 사유
