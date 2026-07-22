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

# MDA-10 권위 규칙: 트렌드 상승/주류 판단의 근거는 T1(업계지)·T2(에디토리얼)만 인용한다.
# 공식몰(T3)은 벤치마크 실측·Design Map용이지 트렌드 근거가 아니다. 저권위(T4) 웹·블로그는
# 어떤 트렌드 주장에도 근거로 쓰지 않는다. 국내 동향은 NAVER 신호로만 말한다.
AUTHORITY_RULE = (
    "권위 규칙: 트렌드(상승/주류/포화/둔화)의 근거 evidence는 tier 1(업계지)·tier 2(에디토리얼)만 "
    "인용한다. 공식몰(tier 3)은 벤치마크 실측·Design Map 근거로만 쓰고 트렌드 근거로 인용하지 않는다. "
    "tier 4(저권위 웹·블로그)는 어떤 트렌드 주장에도 근거로 쓰지 않는다. "
    "T1·T2 근거가 없는 트렌드는 값에 '권위 근거 없음'이라 쓰고 evidence_ids는 빈 배열로 둔다."
)

# LLM 상투어 억제 — 보고서가 컨설팅 슬라이드체로 흐르는 것 방지 (오너 요청 2026-07-21).
STYLE_RULE = (
    "문체 규칙: 건조한 보고체. 매체가 보도한 사실과 실측 수치, 그리고 결론만 쓴다. "
    "금지 표현: '~을 시사한다', '~로 판단된다', '~ 국면', '부상', '주목', '지배', '압도', "
    "'유효 포맷', '컬러 스토리', '~로 보인다', '~하고 있다' 남발. "
    "형용사 수식은 최소화하고, 같은 내용을 두 번 말하지 않는다."
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


def _sanitize(analysis: AnalysisOutput, evidence: list[dict]) -> AnalysisOutput:
    """LLM 출력 후처리: 날조된 evidence id 제거, Design Map 11개 브랜드 행 보장."""
    valid_ids = {e["id"] for e in evidence}
    tier = {e["id"]: e.get("tier", 4) for e in evidence}

    def keep(ids: list[str]) -> list[str]:
        return [i for i in ids if i in valid_ids]

    # 트렌드 근거는 T1·T2(업계지·에디토리얼)만 (MDA-10) — 공식몰(T3)·저권위(T4) 제거.
    for t in analysis.trends:
        t.evidence_ids = [i for i in keep(t.evidence_ids) if tier.get(i, 4) <= 2]
    for a in analysis.actions:
        a.evidence_ids = keep(a.evidence_ids)
    for r in analysis.design_map:
        r.evidence_ids = keep(r.evidence_ids)

    expected = [b.name for b in config.BRANDS if b.auto_collect]
    have = {r.brand for r in analysis.design_map}
    analysis.design_map = [r for r in analysis.design_map if r.brand in set(expected)]
    for name in expected:
        if name not in have:
            analysis.design_map.append(DesignMapRow(
                brand=name, key_items="근거 없음", colors="근거 없음", materials="근거 없음",
                silhouettes="근거 없음", details="근거 없음", price_range="근거 없음",
                evidence_ids=[]))
    order = {n: i for i, n in enumerate(expected)}
    analysis.design_map.sort(key=lambda r: order.get(r.brand, 99))
    return analysis


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
        "(1) 트렌드 테마 정확히 3개 — 개별 기사 나열이 아니라 여러 기사를 관통하는 키워드로 묶는다. "
        "각 테마의 name은 짧은 키워드, rationale은 패션지 에디터의 트렌드 칼럼처럼 4~6문장으로 쓴다: "
        "어떤 매체가 무엇을 보도했는지(아이템·컬러·패턴·실루엣을 구체적으로), 보도들이 어떻게 "
        "하나의 흐름으로 이어지는지, 마지막 한 문장은 한국 25~39 여성 타깃 MD에게 갖는 함의. "
        "테마마다 phase(상승/주류/포화/둔화)를 지정한다. "
        "(2) Design Map — 브랜드별 핵심 아이템/컬러/소재/"
        "실루엣/디테일/가격대 매트릭스, 자동수집 브랜드 11개 각각 한 행씩, "
        "(3) 상품 구성 공백(gaps), (4) 실행 가능한 MD 액션 3개 이상, (5) 데이터 한계(limitations). "
        "타깃(한국 여성 25~39세)과 가격대(20만~70만원) 적합성을 항상 고려한다. "
        "근거 약한 주장은 액션에 넣지 말고 limitations에 '추가 조사 필요'로 내린다. "
        + EVIDENCE_RULE + " " + AUTHORITY_RULE + " " + STYLE_RULE
    )
    user = json.dumps({"researcher_facts": researcher.model_dump()}, ensure_ascii=False) \
        + "\n\n" + _payload(evidence, signals)
    return _sanitize(_call(system, user, AnalysisOutput), evidence)


def _offline_check() -> None:
    """_sanitize 권위 게이팅 (MDA-10) — API 불필요."""
    ev = [
        {"id": "E001", "tier": 1}, {"id": "E002", "tier": 2},
        {"id": "E003", "tier": 3}, {"id": "E004", "tier": 4}, {"id": "E005"},  # tier 결측→4 취급
    ]
    out = AnalysisOutput(
        trends=[Trend(name="Fair Isle", phase="상승", rationale="x",
                      evidence_ids=["E001", "E002", "E003", "E004", "E005", "E999"])],
        design_map=[], gaps=[], actions=[], limitations=[])
    _sanitize(out, ev)
    # 트렌드: T1·T2만 남고 T3(공식몰)·T4(저권위)·결측·날조 제거
    assert out.trends[0].evidence_ids == ["E001", "E002"], out.trends[0].evidence_ids
    # design_map: 자동수집 브랜드 수만큼 백필됨
    assert len(out.design_map) == sum(1 for b in config.BRANDS if b.auto_collect)
    print("analyze offline checks OK")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        _offline_check()
        raise SystemExit(0)
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
