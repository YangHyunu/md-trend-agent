"""공유 필드 폴백 헬퍼. POC_SPEC §12.2 (구조화→LLM→substring 검증)."""
import re
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


# 닫힌 아이템 집합 (canonical ← 동의어 소문자). 색 8계열과 동일 패턴 (MDA-3).
# 'knit'는 기법/형용사라 노이즈(예: "Knit Cashmere Tee") → 동의어에서 제외.
ITEM_SYNONYMS: dict[str, list[str]] = {
    "Sweater":   ["sweater", "pullover", "jumper", "turtleneck",
                  "roll neck", "rollneck", "crewneck", "crew neck",
                  "v-neck", "v neck", "vneck"],
    "Cardigan":  ["cardigan", "cardi"],
    "Top":       ["top", "tee", "t-shirt", "tshirt", "tank", "camisole",
                  "blouse", "shirt", "henley", "polo"],
    "Hoodie":    ["hoodie", "sweatshirt"],
    "Dress":     ["dress", "gown"],
    "Skirt":     ["skirt", "skort"],
    "Pant":      ["pant", "trouser", "jean", "legging", "jogger"],
    "Short":     ["short"],
    "Vest":      ["vest", "gilet"],
    "Jacket":    ["jacket", "blazer", "bomber"],
    "Coat":      ["coat", "parka", "overcoat"],
    "Cape":      ["cape", "poncho"],
    "Scarf":     ["scarf", "scarves", "shawl", "snood", "wrap", "stole"],
    "Hat":       ["hat", "beanie", "cap", "beret", "balaclava", "hood"],
    "Gloves":    ["glove", "mitten"],
    "Warmer":    ["warmer"],
    "Socks":     ["sock"],
    "Underwear": ["knicker", "thong", "brief", "bralette", "bra"],
    "Accessory": ["bag", "belt"],
}
# (키워드, canonical) 평탄화 + 긴 키워드 우선 (t-shirt가 shirt보다, sweatshirt가 shirt보다).
_ITEM_KW: list[tuple[str, str]] = sorted(
    ((kw, canon) for canon, syns in ITEM_SYNONYMS.items() for kw in syns),
    key=lambda x: -len(x[0]),
)


def match_item(text: str | None) -> str | None:
    """text에서 닫힌 아이템 집합을 단어경계로 스캔, 최장 키워드 canonical 반환 (MDA-3)."""
    if not text:
        return None
    t = text.lower()
    for kw, canon in _ITEM_KW:
        # 단어경계(알파벳 경계) + 선택적 복수형(s/es). wool⊂lambswool 오매칭 차단.
        pat = r"(?<![a-z])" + re.escape(kw) + r"(?:s|es)?(?![a-z])"
        if re.search(pat, t):
            return canon
    return None


def extract_item(product_type: str | None, title: str) -> str | None:
    """① product_type 키워드 → ② 비면 title 키워드 → ③ None (MDA-3, LLM 없음).

    비아이템(시즌/소재%/성별)은 조용히 통과하지 않고 None. 미매칭 큐 승격은 MDA-7.
    """
    return match_item(product_type) or match_item(title)


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
