"""사람확인 큐 + override 자기학습 루프. 필드 불문 재사용(item/color/silhouette) (MDA-7).

에스컬레이션: OVERRIDE(즉시 확정) → KEYWORD(닫힌집합) →
(미매칭 누적이 임계 N 이상일 때만) LLM 트리아지(제안만, 자동확정 아님) → None + 큐 승격.
overrides에 값이 있으면 재질문(재큐잉) 없음.
"""
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Callable

IGNORE = "IGNORE"  # override 값: 진짜 비값(시즌/소재% 등)이라 무시하라는 사람 판정

LLMTriageFn = Callable[[str], str]
KeywordFn = Callable[[str], "str | None"]


@dataclass
class QueueEntry:
    field: str
    brand: str
    raw_value: str
    source: str
    count: int = 0
    distinct: int = 0
    llm_suggestion: str | None = None
    _seen: set = dc_field(default_factory=set, repr=False, compare=False)

    def to_dict(self) -> dict:
        d = {"field": self.field, "brand": self.brand, "raw_value": self.raw_value,
             "source": self.source, "count": self.count, "distinct": self.distinct}
        if self.llm_suggestion is not None:
            d["llm_suggestion"] = self.llm_suggestion
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "QueueEntry":
        return cls(field=d["field"], brand=d["brand"], raw_value=d["raw_value"],
                   source=d["source"], count=d.get("count", 0),
                   distinct=d.get("distinct", 0), llm_suggestion=d.get("llm_suggestion"))


class ReviewQueue:
    """미매칭 raw_value를 (field, brand, raw_value) 단위로 누적 — distinct 문자열 단위, 상품 중복제거."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], QueueEntry] = {}

    @classmethod
    def load(cls, path: str | Path) -> "ReviewQueue":
        q = cls()
        p = Path(path)
        if p.exists():
            for d in json.loads(p.read_text(encoding="utf-8") or "[]"):
                e = QueueEntry.from_dict(d)
                q._entries[(e.field, e.brand, e.raw_value)] = e
        return q

    def save(self, path: str | Path) -> None:
        entries = [e.to_dict() for e in self._entries.values()]
        Path(path).write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, *, field: str, brand: str, raw_value: str, source: str,
              product_id: str | None = None) -> QueueEntry:
        """raw_value 미매칭 1건 기록. product_id 있으면 상품 중복제거로 distinct 갱신."""
        key = (field, brand, raw_value)
        e = self._entries.get(key)
        if e is None:
            e = QueueEntry(field=field, brand=brand, raw_value=raw_value, source=source)
            self._entries[key] = e
        e.count += 1
        if product_id:
            e._seen.add(product_id)
            e.distinct = len(e._seen)
        else:
            e.distinct = e.count
        return e

    def get(self, field: str, brand: str, raw_value: str) -> QueueEntry | None:
        return self._entries.get((field, brand, raw_value))

    def entries(self) -> list[QueueEntry]:
        return list(self._entries.values())


def load_overrides(path: str | Path) -> dict[str, str]:
    """item_overrides.json → {raw_value(소문자) → canonical | IGNORE}."""
    p = Path(path)
    if not p.exists():
        return {}
    raw: dict = json.loads(p.read_text(encoding="utf-8") or "{}")
    return {str(k).strip().lower(): v for k, v in raw.items()}


def save_overrides(path: str | Path, overrides: dict[str, str]) -> None:
    Path(path).write_text(json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True),
                          encoding="utf-8")


def map_or_queue(raw_value: str | None, *, field: str, brand: str, source: str,
                 keyword_fn: KeywordFn, overrides: dict[str, str], queue: ReviewQueue,
                 product_id: str | None = None, threshold: int = 10,
                 llm_fn: LLMTriageFn | None = None) -> str | None:
    """OVERRIDE → KEYWORD → (미매칭 누적 ≥ threshold일 때만 LLM 트리아지, 제안만 기록) → None+큐.

    override가 있으면 KEYWORD/큐 단계로 가지 않음(재질문 방지). IGNORE는 None을 돌려주되
    큐에는 올리지 않음(이미 사람이 비값이라 판정).
    """
    if not raw_value or not raw_value.strip():
        return None
    raw = raw_value.strip()
    override = overrides.get(raw.lower())
    if override is not None:
        return None if override == IGNORE else override

    canon = keyword_fn(raw)
    if canon:
        return canon

    entry = queue.record(field=field, brand=brand, raw_value=raw, source=source,
                         product_id=product_id)
    if llm_fn is not None and entry.count >= threshold and entry.llm_suggestion is None:
        entry.llm_suggestion = llm_fn(raw)
    return None


@dataclass
class NormalizedField:
    """정규화 필드 디스크립터 — 필드마다 다른 것만 담고, 큐/override/트리아지는 normalize()가 공용 처리 (MDA-7).

    필드 추가 = (vocab)keyword_fn + (소스)extract 두 개만. item/color/silhouette 전부 이걸로 붙음.
    """
    name: str                                             # "item" | "color" | "silhouette"
    keyword_fn: KeywordFn                                 # 닫힌 어휘셋 매처 (raw → canonical | None)
    extract: Callable[[dict], list[tuple[str | None, str]]]  # product → [(raw, source_label)] 우선순위순
    multi_value: bool = False                             # item=False(첫 canon), color/silhouette=True(전부 수집)


def normalize(spec: NormalizedField, product: dict, *, brand: str,
              queue: "ReviewQueue", overrides: dict[str, str],
              product_id: str | None = None, threshold: int = 10,
              llm_fn: LLMTriageFn | None = None):
    """디스크립터 하나로 OVERRIDE→KEYWORD→트리아지→큐 공용 실행 (MDA-7 단일경로).

    single_value: 소스 순회하며 첫 canon 반환(없으면 None).
    multi_value: 모든 raw 후보의 canon 수집(순서유지·중복제거). 미매칭 raw는 각각 큐로.
    """
    results: list[str] = []
    for raw, source in spec.extract(product):
        canon = map_or_queue(raw, field=spec.name, brand=brand, source=source,
                             keyword_fn=spec.keyword_fn, overrides=overrides, queue=queue,
                             product_id=product_id, threshold=threshold, llm_fn=llm_fn)
        if canon:
            if not spec.multi_value:
                return canon
            if canon not in results:
                results.append(canon)
    return results if spec.multi_value else None


def render_coverage_line(unmatched: int, total: int, *, label: str = "아이템") -> str:
    """§3-b 커버리지 배지 — 미확인 비율에 비례한 3단계(POC_SPEC MDA-7).

    ≥20%: 강조(🔴), 5~20%: 접이식(🟡), <5%: 각주형 저강조(⚪). unmatched=0이면 표시 없음.
    """
    if total <= 0 or unmatched <= 0:
        return ""
    ratio = unmatched / total
    pct = round(ratio * 100)
    if ratio >= 0.20:
        return f"> 🔴 **{label} 확인 필요 {unmatched}건** (미확인 {pct}%)"
    if ratio >= 0.05:
        return (f"<details><summary>🟡 {label} 확인 대기 {unmatched}건 (미확인 {pct}%)</summary>"
                f"사람확인 큐(item_review_queue.json) 참조</details>")
    return f"_(⚪ {label} 확인 대기 {unmatched}건, 미확인 {pct}%)_"
