"""LLM#2 합성 경계 — SPEC_V3 §8: merge 번들 → 3분류 claims + 갭 + 액션.

판정 정합은 결정론이 소유한다(§8.3): classify/demand_supply_gap이 번들에서 verdict를
계산하고, LLM이 낸 classification은 validator가 이 verdict와 대조해 불일치 시 폐기한다.
LLM은 서술(statement/rationale)만 소유한다. M1 corpus.py의 pydantic+validator 분리 선례.
"""
import json
from typing import Literal

from pydantic import BaseModel, Field

from poc import config
from poc.analyze import _call

# 수요 "미미"(빈자리) = 선행신호 후보 direction (§3.2). None = 시그널 부재(축 실패/무시그널).
_LEADING_DIRECTIONS = {"small_base", "insufficient", "flat", None}


def concept_id(cm: dict) -> str:
    """concept 식별자 = label_ko (번들 by_group 조인 키, M4 concept_weekly 계약)."""
    return cm["concept"]["label_ko"]


def _direction(cm: dict) -> str | None:
    naver = cm.get("naver")
    return naver["direction"] if naver else None


def classify(cm: dict, had_prior: bool) -> str | None:
    """번들 측정치 → 3분류 verdict (§8.2). 어느 버킷에도 안 맞으면 None(미분류).

    - validated: 에디토리얼 히트 + 수요 상승(up)
    - leading:   에디토리얼 히트 + 수요 0/미미(small_base/insufficient/flat/무시그널) — 선행신호
    - fading:    직전 주 존재 + 에디토리얼 퇴장(0) + 수요 하락(down)
    """
    editorial = cm["editorial_count"]
    direction = _direction(cm)
    if editorial > 0 and direction == "up":
        return "validated"
    if editorial > 0 and direction in _LEADING_DIRECTIONS:
        return "leading"
    if had_prior and editorial == 0 and direction == "down":
        return "fading"
    return None


def demand_supply_gap(cm: dict) -> bool:
    """수요 상승인데 11브랜드 공급 희박(≤SUPPLY_SCARCE_MAX) = 기회 (§8.2).

    supply None(어휘 갭·미측정)은 갭 판정 불가 → False. 0(측정된 공급 없음)은 갭.
    """
    if _direction(cm) != "up":
        return False
    supply = cm.get("supply")
    if not supply or supply.get("supply_count") is None:
        return False
    return supply["supply_count"] <= config.SUPPLY_SCARCE_MAX


class ConceptClaim(BaseModel):
    concept_id: str
    classification: Literal["validated", "leading", "fading"]
    statement: str
    direction: str | None = None      # 주장한 NAVER 방향 — validator가 번들과 대조
    delta_pct: float | None = None    # 주장한 변동% — validator 대조
    supply_count: int | None = None   # 주장한 공급 count — validator 대조
    demand_supply_gap: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    rationale: str


class SynthAction(BaseModel):
    concept_id: str
    recommendation: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)


class SynthesisOutput(BaseModel):
    claims: list[ConceptClaim]
    actions: list[SynthAction]
    limitations: list[str] = Field(default_factory=list)


def valid_refs_for(cm: dict) -> set[str]:
    """claim이 인용 가능한 EvidenceRef 집합 — 에디토리얼 trace + 측정축 참조."""
    cid = concept_id(cm)
    refs = set(cm["concept"].get("source_refs", []))
    if cm.get("naver"):
        refs.add(f"naver:{cid}")
    supply = cm.get("supply")
    if supply and not supply.get("unmeasurable", False):
        refs.add(f"supply:{cid}")
    return refs


def build_synth_input(bundle: dict, prior_weekly: dict) -> tuple[dict, dict[str, set[str]]]:
    """번들 → LLM#2 입력 payload + {concept_id: valid_ref_set}.

    각 concept에 결정론 verdict(deterministic_classification/demand_supply_gap)와
    인용 가능한 ref 목록을 미리 넣어준다 — LLM은 서술만 채우고 판정은 이미 결정돼 있다.
    prior_weekly: {concept_id: {...}} 직전 주 스냅샷(M4 산출, 빌드 단계 {} 스텁).
    """
    refmap: dict[str, set[str]] = {}
    concepts_payload = []
    for cm in bundle["concepts"]:
        cid = concept_id(cm)
        had_prior = cid in prior_weekly
        refs = valid_refs_for(cm)
        refmap[cid] = refs
        concepts_payload.append({
            "concept_id": cid,
            "label_ko": cm["concept"].get("label_ko"),
            "label_en": cm["concept"].get("label_en"),
            "category": cm["concept"].get("category"),
            "naver": cm.get("naver"),
            "supply": cm.get("supply"),
            "editorial_count": cm["editorial_count"],
            "had_prior_week": had_prior,
            "deterministic_classification": classify(cm, had_prior),
            "demand_supply_gap": demand_supply_gap(cm),
            "valid_evidence_refs": sorted(refs),
        })
    payload = {
        "iso_week": bundle["iso_week"],
        "concepts": concepts_payload,
        "pinterest_category": bundle.get("pinterest_category", []),
        "supply_brands": bundle.get("supply_brands", []),
    }
    return payload, refmap


def _numeric_mismatch(claim: "ConceptClaim", cm: dict) -> str | None:
    """LLM이 주장한 숫자를 번들 원본과 대조 (§8.3). None 주장은 대조 생략."""
    naver = cm.get("naver")
    if claim.direction is not None:
        if not naver or naver["direction"] != claim.direction:
            return "numeric_mismatch:direction"
    if claim.delta_pct is not None:
        actual = naver["delta_pct"] if naver else None
        if actual is None or abs(actual - claim.delta_pct) > config.DELTA_TOLERANCE_PCT:
            return "numeric_mismatch:delta_pct"
    if claim.supply_count is not None:
        supply = cm.get("supply")
        actual = supply["supply_count"] if supply else None
        if actual is None or actual != claim.supply_count:
            return "numeric_mismatch:supply_count"
    return None


def validate_synthesis(output: SynthesisOutput, bundle: dict,
                       prior_weekly: dict) -> tuple[SynthesisOutput, list[dict]]:
    """LLM#2 출력 결정론 검증 (§8.3). 반환: (필터된 출력, 폐기 로그).

    폐기 사유: no_such_concept / duplicate_label_ko / no_valid_evidence /
    classification_mismatch / numeric_mismatch:* / gap_mismatch.
    """
    # concept_id → cm. 중복 label_ko는 신뢰 불가(조인 last-wins) → 폐기 집합.
    by_id: dict[str, dict] = {}
    dup_ids: set[str] = set()
    for cm in bundle["concepts"]:
        cid = concept_id(cm)
        if cid in by_id:
            dup_ids.add(cid)
        by_id[cid] = cm

    dropped: list[dict] = []
    kept_claims: list[ConceptClaim] = []
    kept_ids: set[str] = set()
    for claim in output.claims:
        cid = claim.concept_id
        cm = by_id.get(cid)
        if cm is None:
            dropped.append({"concept_id": cid, "reason": "no_such_concept"})
            continue
        if cid in dup_ids:
            dropped.append({"concept_id": cid, "reason": "duplicate_label_ko"})
            continue
        valid = valid_refs_for(cm)
        if not any(r in valid for r in claim.evidence_refs):
            dropped.append({"concept_id": cid, "reason": "no_valid_evidence"})
            continue
        had_prior = cid in prior_weekly
        if claim.classification != classify(cm, had_prior):
            dropped.append({"concept_id": cid, "reason": "classification_mismatch"})
            continue
        num = _numeric_mismatch(claim, cm)
        if num:
            dropped.append({"concept_id": cid, "reason": num})
            continue
        if claim.demand_supply_gap != demand_supply_gap(cm):
            dropped.append({"concept_id": cid, "reason": "gap_mismatch"})
            continue
        # 인용 ref를 유효 집합으로 정리(날조 ref 제거)
        claim.evidence_refs = [r for r in claim.evidence_refs if r in valid]
        kept_claims.append(claim)
        kept_ids.add(cid)

    kept_actions: list[SynthAction] = []
    for action in output.actions:
        if action.concept_id not in kept_ids:
            dropped.append({"concept_id": action.concept_id, "reason": "action_orphan"})
            continue
        valid = valid_refs_for(by_id[action.concept_id])
        refs = [r for r in action.evidence_refs if r in valid]
        if not refs:
            dropped.append({"concept_id": action.concept_id, "reason": "action_no_valid_evidence"})
            continue
        action.evidence_refs = refs
        kept_actions.append(action)

    return SynthesisOutput(claims=kept_claims, actions=kept_actions,
                           limitations=output.limitations), dropped


SYNTH_SYSTEM = """너는 여성 캐시미어·니트웨어 MD 분석가다. 입력 JSON은 이번 주 측정 번들이다.
각 concept에는 이미 결정론 엔진이 계산한 판정이 들어있다:
- deterministic_classification: 이 개념의 3분류 verdict(validated/leading/fading, null=미분류)
- demand_supply_gap: 수요-공급 갭 여부(bool)
- valid_evidence_refs: 인용 가능한 근거 ref 목록

임무: 각 concept에 대해 claim을 쓴다. 규칙(위반 시 결정론 validator가 폐기):
- classification은 반드시 deterministic_classification 값을 그대로 쓴다. null이면 claim을 만들지 않는다.
- direction/delta_pct/supply_count는 입력 naver/supply 값을 그대로 복사한다(대조됨). 언급 안 할 항목은 null.
- demand_supply_gap도 입력값 그대로.
- evidence_refs에는 valid_evidence_refs 안의 값만 넣는다. 최소 1개. 지어내면 폐기된다.
- statement/rationale만 네 서술이다: 어떤 매체·측정이 이 분류를 뒷받침하는지 건조하게.
  validated=시장 반응 물량 판단, leading=빈자리 선점, fading=축소/정리.
- actions: 근거 있는 MD 액션. concept_id는 claims의 것 중 하나, evidence_refs는 valid_evidence_refs만.
- limitations: 측정 한계(축 실패/어휘 갭 등).
문체: 건조한 보고체. 상투어 금지."""


def run_synthesis(bundle: dict, prior_weekly: dict) -> tuple[SynthesisOutput, list[dict]]:
    """번들 → LLM#2 합성 → 결정론 검증. 반환: (검증된 출력, 폐기 로그)."""
    payload, _ = build_synth_input(bundle, prior_weekly)
    raw = _call(SYNTH_SYSTEM, json.dumps(payload, ensure_ascii=False), SynthesisOutput)
    return validate_synthesis(raw, bundle, prior_weekly)


def _load_prior_weekly() -> dict:
    """직전 주 concept_weekly 스냅샷 = M4 산출물. 빌드 단계 스텁 {} (M4 착지 후 배선).

    SEAM: M4가 sqlite driver.get_prior_weeks로 {concept_id: {...}}를 반환하도록 교체.
    """
    return {}


def synthesize_bundle(bundle_dict: dict, prior_weekly: dict) -> dict:
    """번들 dict → LLM#2 합성 → out 저장. LLM 실패는 격리(§4.4): 번들은 이미 저장돼 있다."""
    try:
        out, dropped = run_synthesis(bundle_dict, prior_weekly)
    except Exception as exc:
        (config.OUT_DIR / "synthesis_dropped.json").write_text(
            json.dumps([{"reason": "llm_failed", "error": f"{type(exc).__name__}: {exc}"}],
                       ensure_ascii=False, indent=2))
        return {"claims": 0, "dropped": 0, "fallback": f"{type(exc).__name__}: {exc}"}
    (config.OUT_DIR / "synthesis.json").write_text(
        out.model_dump_json(indent=2), encoding="utf-8")
    (config.OUT_DIR / "synthesis_dropped.json").write_text(
        json.dumps(dropped, ensure_ascii=False, indent=2))
    return {"claims": len(out.claims), "dropped": len(dropped)}


def exit_code(result: dict) -> int:
    """cron 경보(§15): fallback(LLM 실패)은 1 — 부분 report를 은폐하지 않는다."""
    return 1 if "fallback" in result else 0


if __name__ == "__main__":
    bundle_dict = json.loads((config.OUT_DIR / "merge_bundle.json").read_text(encoding="utf-8"))
    _result = synthesize_bundle(bundle_dict, _load_prior_weekly())
    print(json.dumps(_result, ensure_ascii=False))
    raise SystemExit(exit_code(_result))
