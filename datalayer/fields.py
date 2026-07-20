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


def pick_structured_colors(options: list[dict]) -> list[str]:
    """options 중 name이 color/colour(철자 방어)인 것의 values."""
    for o in options:
        if str(o.get("name", "")).strip().lower() in ("color", "colour"):
            return [str(v).strip() for v in o.get("values", []) if str(v).strip()]
    return []


def verify_substring(token: str, raw_blob: str) -> bool:
    """LLM 추출 색이 원본에 실제 존재하는지 (날조 차단, §12.2)."""
    return bool(token) and token.lower() in raw_blob.lower()


def llm_color_fallback(title: str, tags: list[str], raw_blob: str,
                       llm_fn: LLMFn) -> list[str]:
    prompt = (
        "다음 상품 텍스트에서 색상명만 쉼표로 나열하라. 색이 없으면 빈 줄.\n"
        f"제목: {title}\n태그: {', '.join(tags)}"
    )
    out = llm_fn(prompt) or ""
    cands = [c.strip() for c in out.split(",") if c.strip()]
    return [c for c in cands if verify_substring(c, raw_blob)]


def extract_colors(options: list[dict], title: str, tags: list[str],
                   raw_blob: str, llm_fn: LLMFn | None = None) -> list[str]:
    """① 구조화 options → ② LLM 추출 + substring 검증 (§12.2)."""
    structured = pick_structured_colors(options)
    if structured:
        return structured
    if llm_fn is None:
        return []
    return llm_color_fallback(title, tags, raw_blob, llm_fn)
