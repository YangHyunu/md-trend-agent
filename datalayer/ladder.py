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
