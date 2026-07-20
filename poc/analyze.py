"""LLM 2패스: 리서처(사실 정리) → MD 분석가(트렌드/Design Map/액션)."""
import json
import sys
from typing import Literal

import anthropic
from pydantic import BaseModel

from poc import config

MODEL = "claude-opus-4-8"


class Fact(BaseModel):
    statement: str
    evidence_ids: list[str]
    brand: str | None = None


class ResearcherOutput(BaseModel):
    facts: list[Fact]


class Trend(BaseModel):
    name: str
    phase: Literal["상승", "주류", "포화", "둔화"]
    rationale: str
    evidence_ids: list[str]


class DesignMapRow(BaseModel):
    brand: str
    key_items: str
    colors: str
    materials: str
    silhouettes: str
    details: str
    price_range: str
    evidence_ids: list[str]


class Action(BaseModel):
    recommendation: str
    rationale: str
    evidence_ids: list[str]


class AnalysisOutput(BaseModel):
    trends: list[Trend]
    design_map: list[DesignMapRow]
    gaps: list[str]
    actions: list[Action]
    limitations: list[str]


EVIDENCE_RULE = (
    "근거 규칙: 모든 주장과 셀에는 반드시 입력으로 제공된 evidence id(E001 형식)만 인용한다. "
    "근거가 없는 항목은 값에 '근거 없음'이라고 쓰고 evidence_ids는 빈 배열로 둔다. "
    "id를 지어내지 않는다. NAVER ratio는 상대값이므로 서로 다른 요청 간 절대 비교하지 않는다."
)


def _call(system: str, user: str, output_format):
    client = anthropic.Anthropic()
    last_err = None
    for _ in range(2):  # 1회 + 스키마 실패 시 재시도 1회 (POC_SPEC §7)
        try:
            resp = client.messages.parse(
                model=MODEL,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_format,
            )
            if resp.parsed_output is None:
                raise ValueError(f"파싱 실패 stop_reason={resp.stop_reason}")
            return resp.parsed_output
        except Exception as e:
            last_err = e
    raise last_err


def _payload(evidence: list[dict], signals: list[dict]) -> str:
    return json.dumps({
        "analysis_conditions": config.ANALYSIS,
        "brands": [{"name": b.name, "purpose": b.purpose} for b in config.BRANDS if b.auto_collect],
        "naver_signals": signals,
        "evidence": evidence,
    }, ensure_ascii=False)


def run_researcher(evidence: list[dict], signals: list[dict]) -> ResearcherOutput:
    system = (
        "너는 패션 리서처다. 수집된 웹 발췌와 NAVER 수요 신호에서 사실만 정리한다. "
        "해석/추측 금지 — 발췌에 실제로 나타난 상품명, 소재, 컬러, 실루엣, 가격, 수치를 "
        "간결한 사실 문장으로 추출한다. 중복은 병합한다. " + EVIDENCE_RULE
    )
    return _call(system, _payload(evidence, signals), ResearcherOutput)


def run_analyst(researcher: ResearcherOutput, evidence: list[dict],
                signals: list[dict]) -> AnalysisOutput:
    system = (
        "너는 여성 캐시미어·니트웨어 브랜드의 MD 분석가 겸 에디터다. "
        "리서처가 정리한 사실과 원본 근거를 바탕으로 다음을 작성한다: "
        "(1) 트렌드(상승/주류/포화/둔화 구분), (2) Design Map — 브랜드별 핵심 아이템/컬러/소재/"
        "실루엣/디테일/가격대 매트릭스, 자동수집 브랜드 11개 각각 한 행씩, "
        "(3) 상품 구성 공백(gaps), (4) 실행 가능한 MD 액션 3개 이상, (5) 데이터 한계(limitations). "
        "타깃(한국 여성 25~39세)과 가격대(20만~70만원) 적합성을 항상 고려한다. "
        "근거 약한 주장은 액션에 넣지 말고 limitations에 '추가 조사 필요'로 내린다. " + EVIDENCE_RULE
    )
    user = json.dumps({"researcher_facts": researcher.model_dump()}, ensure_ascii=False) \
        + "\n\n" + _payload(evidence, signals)
    return _call(system, user, AnalysisOutput)


if __name__ == "__main__":
    config.OUT_DIR.mkdir(exist_ok=True)
    if "--fixture" in sys.argv:
        evidence = [
            {"id": "E001", "url": "https://extreme-cashmere.com/", "brand": "Extreme cashmere",
             "source_type": "official", "fetched_at": "2026-07-20",
             "excerpt": "n°316 lana sweater, brushed cashmere, colors: lilac, pistachio, tomato. €420. Oversized unisex fit."},
            {"id": "E002", "url": "https://www.quince.com/women/cashmere", "brand": "Quince",
             "source_type": "official", "fetched_at": "2026-07-20",
             "excerpt": "Mongolian Cashmere Crewneck Sweater $49.90. 100% grade-A cashmere. Classic fit, 20 colors."},
        ]
        signals = [{"source": "shopping_keyword", "group": "캐시미어니트",
                    "series": [{"period": "2026-06-01", "ratio": 100.0}],
                    "requested_segment": "25-39", "observed_segment": "20-39",
                    "coverage_mismatch": True, "note": "상대값"}]
    else:
        evidence = json.loads((config.OUT_DIR / "evidence.json").read_text(encoding="utf-8"))
        naver = json.loads((config.OUT_DIR / "naver_raw.json").read_text(encoding="utf-8"))
        signals = naver["signals"]
    r = run_researcher(evidence, signals)
    (config.OUT_DIR / "researcher.json").write_text(
        r.model_dump_json(indent=2), encoding="utf-8")
    print(f"researcher facts={len(r.facts)}")
    a = run_analyst(r, evidence, signals)
    (config.OUT_DIR / "analysis.json").write_text(
        a.model_dump_json(indent=2), encoding="utf-8")
    print(f"analyst trends={len(a.trends)} rows={len(a.design_map)} actions={len(a.actions)}")
