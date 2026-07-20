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
