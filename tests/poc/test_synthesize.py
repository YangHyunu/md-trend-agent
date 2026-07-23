"""LLM#2 합성 경계 테스트 (SPEC_V3 §8) — 결정론 부분만. LLM 호출은 monkeypatch."""
import json
from pathlib import Path

from poc.synthesize import (ConceptClaim, SynthAction, SynthesisOutput, build_synth_input,
                            classify, concept_id, demand_supply_gap, validate_synthesis,
                            valid_refs_for)

FIX = Path(__file__).parent / "fixtures" / "merge_bundle_golden.json"


# --- Task 1: classify / demand_supply_gap / concept_id ---

def _cm(editorial=1, direction="up", supply=None):
    naver = {"direction": direction, "delta_pct": None, "series": [],
             "recent_mean": None, "prior_mean": None} if direction else None
    return {"concept": {"label_ko": "포인텔 니트", "label_en": "pointelle knit"},
            "naver": naver, "editorial_count": editorial,
            "supply": {"supply_count": supply, "facets": {}, "unmeasurable": supply is None}}


def test_classify_validated_editorial_hit_demand_up():
    assert classify(_cm(editorial=2, direction="up"), had_prior=False) == "validated"


def test_classify_leading_editorial_hit_demand_absent():
    assert classify(_cm(editorial=1, direction="small_base"), had_prior=False) == "leading"
    assert classify(_cm(editorial=1, direction="insufficient"), had_prior=False) == "leading"
    assert classify(_cm(editorial=1, direction="flat"), had_prior=False) == "leading"
    assert classify(_cm(editorial=1, direction=None), had_prior=False) == "leading"


def test_classify_fading_prior_editorial_gone_demand_down():
    assert classify(_cm(editorial=0, direction="down"), had_prior=True) == "fading"


def test_classify_none_when_no_bucket_matches():
    assert classify(_cm(editorial=0, direction="down"), had_prior=False) is None   # fading needs prior
    assert classify(_cm(editorial=0, direction="up"), had_prior=False) is None      # no editorial → not validated
    assert classify(_cm(editorial=2, direction="down"), had_prior=False) is None    # editorial+down = no bucket


def test_demand_supply_gap_true_when_demand_up_supply_scarce():
    assert demand_supply_gap(_cm(direction="up", supply=1)) is True
    assert demand_supply_gap(_cm(direction="up", supply=0)) is True


def test_demand_supply_gap_false_when_supply_ample_or_demand_flat():
    assert demand_supply_gap(_cm(direction="up", supply=5)) is False
    assert demand_supply_gap(_cm(direction="flat", supply=0)) is False


def test_concept_id_is_label_ko():
    assert concept_id(_cm()) == "포인텔 니트"


# --- Task 2: schema + input builder ---

def _bundle_cm():
    return {"concept": {"label_ko": "포인텔 니트", "label_en": "pointelle knit",
                        "source_refs": ["a0000000001", "w0"]},
            "naver": {"direction": "up", "delta_pct": 42.0, "series": [{"period": "2026-06-01", "ratio": 10}],
                      "recent_mean": 20.0, "prior_mean": 14.0},
            "supply": {"supply_count": 1, "facets": {}, "unmeasurable": False},
            "editorial_count": 1}


def _bundle():
    return {"schema_version": "3.0", "iso_week": "2026-W30", "generated_at": "x",
            "concepts": [_bundle_cm()], "pinterest_category": [],
            "supply_brands": [{"brand": "Quince", "count": 3}],
            "coverage": {}}


def test_valid_refs_include_source_naver_supply():
    refs = valid_refs_for(_bundle_cm())
    assert "a0000000001" in refs and "w0" in refs
    assert "naver:포인텔 니트" in refs and "supply:포인텔 니트" in refs


def test_valid_refs_omit_supply_when_unmeasurable():
    cm = _bundle_cm()
    cm["supply"] = {"supply_count": None, "facets": {}, "unmeasurable": True}
    assert "supply:포인텔 니트" not in valid_refs_for(cm)


def test_build_synth_input_exposes_verdict_and_refmap():
    payload, refmap = build_synth_input(_bundle(), prior_weekly={})
    assert payload["iso_week"] == "2026-W30"
    c0 = payload["concepts"][0]
    assert c0["deterministic_classification"] == "validated"
    assert c0["demand_supply_gap"] is True
    assert c0["valid_evidence_refs"]
    assert refmap["포인텔 니트"] == valid_refs_for(_bundle_cm())


def test_synthesis_output_schema_round_trips():
    out = SynthesisOutput(
        claims=[ConceptClaim(concept_id="포인텔 니트", classification="validated",
                             statement="s", direction="up", delta_pct=42.0, supply_count=1,
                             demand_supply_gap=True, evidence_refs=["a0000000001"], rationale="r")],
        actions=[SynthAction(concept_id="포인텔 니트", recommendation="발주", rationale="r",
                             evidence_refs=["a0000000001"])],
        limitations=["l"])
    restored = SynthesisOutput.model_validate_json(out.model_dump_json())
    assert restored.claims[0].classification == "validated"


# --- Task 3: validator ---

def _claim(**kw):
    base = dict(concept_id="포인텔 니트", classification="validated", statement="s",
                direction="up", delta_pct=42.0, supply_count=1, demand_supply_gap=True,
                evidence_refs=["a0000000001"], rationale="r")
    base.update(kw)
    return ConceptClaim(**base)


def _out(claims, actions=None):
    return SynthesisOutput(claims=claims, actions=actions or [], limitations=[])


def test_valid_claim_survives():
    kept, dropped = validate_synthesis(_out([_claim()]), _bundle(), {})
    assert len(kept.claims) == 1 and dropped == []


def test_claim_dropped_when_concept_absent():
    kept, dropped = validate_synthesis(_out([_claim(concept_id="없는개념")]), _bundle(), {})
    assert kept.claims == [] and dropped[0]["reason"] == "no_such_concept"


def test_claim_dropped_without_valid_evidence():
    kept, dropped = validate_synthesis(_out([_claim(evidence_refs=["ZZZ"])]), _bundle(), {})
    assert kept.claims == [] and dropped[0]["reason"] == "no_valid_evidence"


def test_claim_dropped_on_classification_mismatch():
    kept, dropped = validate_synthesis(_out([_claim(classification="leading")]), _bundle(), {})
    assert kept.claims == [] and dropped[0]["reason"] == "classification_mismatch"


def test_claim_dropped_on_numeric_mismatch():
    kept, dropped = validate_synthesis(_out([_claim(delta_pct=999.0)]), _bundle(), {})
    assert kept.claims == [] and dropped[0]["reason"].startswith("numeric_mismatch")


def test_claim_dropped_on_supply_count_mismatch():
    kept, dropped = validate_synthesis(_out([_claim(supply_count=99)]), _bundle(), {})
    assert kept.claims == [] and dropped[0]["reason"] == "numeric_mismatch:supply_count"


def test_claim_dropped_on_gap_mismatch():
    kept, dropped = validate_synthesis(_out([_claim(demand_supply_gap=False)]), _bundle(), {})
    assert kept.claims == [] and dropped[0]["reason"] == "gap_mismatch"


def test_null_numeric_fields_skip_that_check():
    kept, dropped = validate_synthesis(
        _out([_claim(direction=None, delta_pct=None, supply_count=None)]), _bundle(), {})
    assert len(kept.claims) == 1


def test_duplicate_label_ko_bundle_flagged():
    b = _bundle()
    b["concepts"] = [_bundle_cm(), _bundle_cm()]
    kept, dropped = validate_synthesis(_out([_claim()]), b, {})
    assert kept.claims == []
    assert any(d["reason"] == "duplicate_label_ko" for d in dropped)


def test_action_dropped_when_concept_dropped():
    out = _out([_claim(concept_id="없는개념")],
               actions=[SynthAction(concept_id="없는개념", recommendation="x",
                                    rationale="r", evidence_refs=["a0000000001"])])
    kept, dropped = validate_synthesis(out, _bundle(), {})
    assert kept.actions == []


# --- Task 4: golden fixture + run_synthesis ---

def test_golden_bundle_deterministic_verdicts():
    bundle = json.loads(FIX.read_text())
    prior = {"크롭 가디건": {"iso_week": "2026-W29"}}
    payload, refmap = build_synth_input(bundle, prior)
    verdicts = {c["concept_id"]: c["deterministic_classification"]
                for c in payload["concepts"]}
    assert verdicts["캐시미어 니트"] == "validated"
    assert verdicts["포인텔 니트"] == "leading"
    assert verdicts["크롭 가디건"] == "fading"
    # 포인텔: 수요 미미(small_base=시그널은 존재)라 naver ref 유효, supply는 unmeasurable→제외
    assert refmap["포인텔 니트"] == {"a0000000002", "naver:포인텔 니트"}


def test_run_synthesis_validates_llm_output(monkeypatch):
    bundle = json.loads(FIX.read_text())
    prior = {"크롭 가디건": {"iso_week": "2026-W29"}}
    from poc import synthesize
    fake = SynthesisOutput(claims=[
        ConceptClaim(concept_id="캐시미어 니트", classification="validated", statement="s",
                     direction="up", delta_pct=42.0, supply_count=12, demand_supply_gap=False,
                     evidence_refs=["a0000000001", "naver:캐시미어 니트"], rationale="r"),
        ConceptClaim(concept_id="포인텔 니트", classification="leading", statement="s",
                     direction=None, delta_pct=None, supply_count=None, demand_supply_gap=False,
                     evidence_refs=["a0000000002"], rationale="r"),
        ConceptClaim(concept_id="캐시미어 니트", classification="leading", statement="bad",
                     direction="up", delta_pct=42.0, supply_count=12, demand_supply_gap=False,
                     evidence_refs=["a0000000001"], rationale="r"),
    ], actions=[], limitations=[])
    monkeypatch.setattr(synthesize, "_call", lambda *a, **k: fake)
    out, dropped = synthesize.run_synthesis(bundle, prior)
    assert len(out.claims) == 2
    assert any(d["reason"] == "classification_mismatch" for d in dropped)
