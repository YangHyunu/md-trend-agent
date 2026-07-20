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
