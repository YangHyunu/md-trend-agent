"""정규화 상품 레코드. POC_SPEC §12.4 브랜드 블록의 입력."""
from dataclasses import dataclass, field


@dataclass
class ProductRecord:
    brand: str
    url: str
    item: str | None                 # product_type (없으면 None)
    colors_raw: list[str]            # 원색명 (근거 보존)
    price_native: float | None       # shop 통화 기준 금액
    currency: str | None             # ISO 코드 (USD/EUR/GBP)
    compare_at_native: float | None  # 정가 (세일 감지용)
    on_sale: bool
    materials: list[str]             # 소재 키워드
    published_at: str | None         # ISO 날짜 (YYYY-MM-DD)
    source: str                      # 성공한 rung (예 "shopify")
    silhouettes: list[str] = field(default_factory=list)  # 핏/볼륨 (MDA-4 rung1)
    colors_family: list[str] = field(default_factory=list)  # 8계열 매핑 (MDA-8)
    image_url: str | None = None     # 대표 이미지 (피드 첫 이미지 — 보고서 썸네일용)


@dataclass
class BrandExtractionResult:
    brand: str
    source: str | None                          # 성공 rung, 전부 실패 시 None
    products: list[ProductRecord] = field(default_factory=list)
    failure: str | None = None                  # 전 rung 실패 시 사유
