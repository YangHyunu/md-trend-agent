# M3 Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM#2 synthesis boundary — merge bundle → validated/leading/fading 3-class claims + demand-supply gap + actions, with a deterministic validator that owns the verdict.

**Architecture:** Mirror M1 corpus (`poc/corpus.py`): a pydantic LLM output + a *separate* pure-deterministic validator. The LLM writes narrative; determinism computes the 3-class verdict from the bundle and drops any claim whose classification/numbers don't match the bundle. New module `poc/synthesize.py`; `poc/weekly.py` gains one independent synth function after bundle assembly; `poc/config.py` gets append-only constants.

**Tech Stack:** Python 3.11+, pydantic, anthropic SDK (`poc.analyze._call`, model `claude-opus-4-8`), pytest.

## Global Constraints

- Determinism owns judgment (SPEC_V3 §3.1, §8.3): fetch/parse/measure/merge/validate have **no LLM**. LLM#2 writes `statement`/`rationale` only; the 3-class verdict, demand-supply gap, and numeric facts are recomputed deterministically and cross-checked.
- Concept identity = `label_ko` (bundle `by_group` already keys on it, `poc/bundle.py:88`).
- Every claim needs ≥1 valid EvidenceRef or it is dropped + logged (§8.3).
- Numeric assertions (direction, delta_pct, supply_count) must match bundle values within `config.DELTA_TOLERANCE_PCT`; mismatch → drop + log.
- Failure isolation (§4.4 / §85): LLM#2 death → partial output (measurement bundle survives), fallback recorded — mirror `corpus.main` fallback dict.
- Test interpreter: `python3 -m pytest` (worktree has no `.venv`). Baseline = 189 passing.
- Only-conflict file with M4 = `poc/weekly.py`; keep synth as an independent function so a later rebase is trivial. `poc/config.py` additions are append-only.
- Contract to M4: each kept claim carries `concept_id` + `classification` → `concept_weekly.classification`.

---

### Task 1: Config constants + deterministic `classify()` / `demand_supply_gap()`

**Files:**
- Modify: `poc/config.py` (append at end)
- Create: `poc/synthesize.py`
- Test: `tests/poc/test_synthesize.py`

**Interfaces:**
- Consumes: `ConceptMeasurement` shape from `poc/bundle.py` (dict form: `{"concept": {...}, "naver": {...}|None, "supply": {...}|None, "editorial_count": int}`).
- Produces:
  - `config.SUPPLY_SCARCE_MAX: int` (=2), `config.DELTA_TOLERANCE_PCT: float` (=0.1)
  - `synthesize.classify(cm: dict, had_prior: bool) -> str | None` — returns `"validated"|"leading"|"fading"|None`
  - `synthesize.demand_supply_gap(cm: dict) -> bool`
  - `synthesize.concept_id(cm: dict) -> str` — returns `cm["concept"]["label_ko"]`

- [ ] **Step 1: Write the failing test**

```python
# tests/poc/test_synthesize.py
from poc.synthesize import classify, demand_supply_gap, concept_id


def _cm(editorial=1, direction="up", supply=None):
    naver = {"direction": direction, "delta_pct": None, "series": [],
             "recent_mean": None, "prior_mean": None} if direction else None
    sup = {"supply_count": supply, "facets": {}, "unmeasurable": supply is None} \
        if supply is not None or direction is None else {"supply_count": supply, "facets": {}, "unmeasurable": False}
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'poc.synthesize'`

- [ ] **Step 3: Append config constants**

Append to `poc/config.py`:

```python
# --- M3 합성 3분류 경계 (SPEC_V3 §8.3 — 판정 정합은 결정론 소유) ---
SUPPLY_SCARCE_MAX = 2       # 수요 상승 + 공급 count ≤ 2 = 수요-공급 갭(기회 신호)
DELTA_TOLERANCE_PCT = 0.1   # validator 숫자(변동%) 대조 허용 오차
```

- [ ] **Step 4: Write `classify` / `demand_supply_gap` / `concept_id`**

Create `poc/synthesize.py` (module docstring + these functions):

```python
"""LLM#2 합성 경계 — SPEC_V3 §8: merge 번들 → 3분류 claims + 갭 + 액션.

판정 정합은 결정론이 소유한다(§8.3): classify/demand_supply_gap이 번들에서 verdict를
계산하고, LLM이 낸 classification은 validator가 이 verdict와 대조해 불일치 시 폐기한다.
LLM은 서술(statement/rationale)만 소유한다. M1 corpus.py의 pydantic+validator 분리 선례.
"""
from poc import config

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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/config.py poc/synthesize.py tests/poc/test_synthesize.py
git commit -m "feat(poc): M3 결정론 3분류 classify + 수요-공급 갭 (SPEC_V3 §8.2, §8.3)"
```

---

### Task 2: LLM#2 output schema + input payload builder

**Files:**
- Modify: `poc/synthesize.py`
- Test: `tests/poc/test_synthesize.py`

**Interfaces:**
- Consumes: `classify`, `demand_supply_gap`, `concept_id` from Task 1; `MergeBundle` dict from `poc/bundle.py`.
- Produces:
  - `synthesize.ConceptClaim` (pydantic): `concept_id:str, classification:Literal["validated","leading","fading"], statement:str, direction:str|None, delta_pct:float|None, supply_count:int|None, demand_supply_gap:bool, evidence_refs:list[str], rationale:str`
  - `synthesize.SynthAction` (pydantic): `concept_id:str, recommendation:str, rationale:str, evidence_refs:list[str]`
  - `synthesize.SynthesisOutput` (pydantic): `claims:list[ConceptClaim], actions:list[SynthAction], limitations:list[str]`
  - `synthesize.build_synth_input(bundle: dict, prior_weekly: dict) -> tuple[dict, dict[str, set[str]]]` — returns (LLM input payload, `{concept_id: valid_ref_set}`)
  - `synthesize.valid_refs_for(cm: dict) -> set[str]` — concept `source_refs` ∪ `{f"naver:{cid}"}` if naver ∪ `{f"supply:{cid}"}` if supply measurable

- [ ] **Step 1: Write the failing test**

```python
# append to tests/poc/test_synthesize.py
from poc.synthesize import (SynthesisOutput, ConceptClaim, SynthAction,
                            build_synth_input, valid_refs_for)


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
    # 결정론 verdict를 프롬프트에 명시(§8.3: LLM은 서술만, 판정은 이미 결정됨)
    assert c0["deterministic_classification"] == "validated"
    assert c0["demand_supply_gap"] is True
    assert c0["valid_evidence_refs"]           # 인용 가능한 ref 목록 제공
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: FAIL — `ImportError: cannot import name 'SynthesisOutput'`

- [ ] **Step 3: Add schema + input builder**

Add to `poc/synthesize.py` (imports at top: `from typing import Literal`, `from pydantic import BaseModel, Field`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add poc/synthesize.py tests/poc/test_synthesize.py
git commit -m "feat(poc): M3 LLM#2 출력 스키마 + verdict 주입 입력 빌더 (SPEC_V3 §8.1, §8.2)"
```

---

### Task 3: Deterministic validator (drop rules §8.3)

**Files:**
- Modify: `poc/synthesize.py`
- Test: `tests/poc/test_synthesize.py`

**Interfaces:**
- Consumes: `SynthesisOutput`, `build_synth_input`, `classify`, `demand_supply_gap` from Tasks 1-2.
- Produces:
  - `synthesize.validate_synthesis(output: SynthesisOutput, bundle: dict, prior_weekly: dict) -> tuple[SynthesisOutput, list[dict]]` — returns (filtered output, dropped log). Drop reasons: `no_such_concept`, `duplicate_label_ko`, `no_valid_evidence`, `classification_mismatch`, `numeric_mismatch:direction|delta_pct|supply_count`, `gap_mismatch`. Actions dropped if concept dropped or no valid evidence.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/poc/test_synthesize.py
from poc.synthesize import validate_synthesis


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
    # 번들 verdict=validated 인데 LLM이 leading 주장 → 폐기
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
    # LLM이 direction/delta/supply를 None으로 두면 그 항목은 대조 생략(주장 안 함)
    kept, dropped = validate_synthesis(
        _out([_claim(direction=None, delta_pct=None, supply_count=None)]), _bundle(), {})
    assert len(kept.claims) == 1


def test_duplicate_label_ko_bundle_flagged():
    # M2 백로그: 번들에 label_ko 중복 시 해당 concept claim 폐기 + 로그
    b = _bundle()
    dup = _bundle_cm()
    b["concepts"] = [_bundle_cm(), dup]
    kept, dropped = validate_synthesis(_out([_claim()]), b, {})
    assert kept.claims == []
    assert any(d["reason"] == "duplicate_label_ko" for d in dropped)


def test_action_dropped_when_concept_dropped():
    out = _out([_claim(concept_id="없는개념")],
               actions=[SynthAction(concept_id="없는개념", recommendation="x",
                                    rationale="r", evidence_refs=["a0000000001"])])
    kept, dropped = validate_synthesis(out, _bundle(), {})
    assert kept.actions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: FAIL — `ImportError: cannot import name 'validate_synthesis'`

- [ ] **Step 3: Implement validator**

Add to `poc/synthesize.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add poc/synthesize.py tests/poc/test_synthesize.py
git commit -m "feat(poc): M3 결정론 validator — evidence/숫자/분류 정합 대조 폐기 (SPEC_V3 §8.3)"
```

---

### Task 4: LLM#2 caller + golden fixture regression

**Files:**
- Modify: `poc/synthesize.py`
- Create: `tests/poc/fixtures/merge_bundle_golden.json`
- Test: `tests/poc/test_synthesize.py`

**Interfaces:**
- Consumes: `build_synth_input`, `validate_synthesis`, `SynthesisOutput`; `poc.analyze._call`.
- Produces:
  - `synthesize.SYNTH_SYSTEM: str`
  - `synthesize.run_synthesis(bundle: dict, prior_weekly: dict) -> tuple[SynthesisOutput, list[dict]]` — calls `_call`, then `validate_synthesis`.

- [ ] **Step 1: Write the golden fixture**

Create `tests/poc/fixtures/merge_bundle_golden.json` — a minimal valid bundle with one `validated`, one `leading`, one `fading`-eligible concept (fading needs a prior; golden includes prior stub in the test). Content:

```json
{
  "schema_version": "3.0",
  "iso_week": "2026-W30",
  "generated_at": "2026-07-23T03:00:00+00:00",
  "concepts": [
    {"concept": {"label_ko": "캐시미어 니트", "label_en": "cashmere knit",
                 "category": "소재", "source_refs": ["a0000000001", "w0"]},
     "naver": {"direction": "up", "delta_pct": 42.0,
               "series": [{"period": "2026-06-01", "ratio": 10}],
               "recent_mean": 20.0, "prior_mean": 14.0},
     "supply": {"supply_count": 12, "facets": {}, "unmeasurable": false},
     "editorial_count": 2},
    {"concept": {"label_ko": "포인텔 니트", "label_en": "pointelle knit",
                 "category": "소재", "source_refs": ["a0000000002"]},
     "naver": {"direction": "small_base", "delta_pct": null,
               "series": [{"period": "2026-06-01", "ratio": 1}],
               "recent_mean": 2.0, "prior_mean": 1.0},
     "supply": {"supply_count": null, "facets": {}, "unmeasurable": true},
     "editorial_count": 1},
    {"concept": {"label_ko": "크롭 가디건", "label_en": "cropped cardigan",
                 "category": "아이템", "source_refs": ["a0000000003"]},
     "naver": {"direction": "down", "delta_pct": -30.0,
               "series": [{"period": "2026-06-01", "ratio": 30}],
               "recent_mean": 14.0, "prior_mean": 20.0},
     "supply": {"supply_count": 4, "facets": {}, "unmeasurable": false},
     "editorial_count": 0}
  ],
  "pinterest_category": [],
  "supply_brands": [{"brand": "Quince", "count": 12}],
  "coverage": {}
}
```

- [ ] **Step 2: Write the failing golden test**

```python
# append to tests/poc/test_synthesize.py
import json
from pathlib import Path
from poc.synthesize import build_synth_input, classify

FIX = Path(__file__).parent / "fixtures" / "merge_bundle_golden.json"


def test_golden_bundle_deterministic_verdicts():
    bundle = json.loads(FIX.read_text())
    prior = {"크롭 가디건": {"iso_week": "2026-W29"}}   # fading엔 직전 주 필요
    payload, refmap = build_synth_input(bundle, prior)
    verdicts = {c["concept_id"]: c["deterministic_classification"]
                for c in payload["concepts"]}
    assert verdicts["캐시미어 니트"] == "validated"
    assert verdicts["포인텔 니트"] == "leading"
    assert verdicts["크롭 가디건"] == "fading"
    # 포인텔: 수요 미미(선행) + supply unmeasurable → 갭 False, supply ref 없음
    assert refmap["포인텔 니트"] == {"a0000000002"}


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
                     evidence_refs=["a0000000001"], rationale="r"),   # 분류 불일치 → 폐기
    ], actions=[], limitations=[])
    monkeypatch.setattr(synthesize, "_call", lambda *a, **k: fake)
    out, dropped = synthesize.run_synthesis(bundle, prior)
    assert len(out.claims) == 2
    assert any(d["reason"] == "classification_mismatch" for d in dropped)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: FAIL — `AttributeError: module 'poc.synthesize' has no attribute 'run_synthesis'`

- [ ] **Step 4: Add system prompt + `run_synthesis`**

Add to `poc/synthesize.py` (import at top: `from poc.analyze import _call`, and reuse `config.ANALYSIS`):

```python
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
```

Add `import json` at top of module if not already present.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/poc/test_synthesize.py -q`
Expected: PASS

- [ ] **Step 6: Run full suite (no regression)**

Run: `python3 -m pytest -q`
Expected: PASS (189 baseline + new synthesize tests)

- [ ] **Step 7: Commit**

```bash
git add poc/synthesize.py tests/poc/fixtures/merge_bundle_golden.json tests/poc/test_synthesize.py
git commit -m "feat(poc): M3 LLM#2 caller + golden fixture 계약 회귀 (SPEC_V3 §8.1, §13)"
```

---

### Task 5: weekly.py wiring + CLI + live-verify

**Files:**
- Modify: `poc/weekly.py`
- Modify: `poc/synthesize.py` (add `__main__` + `_load_prior_weekly`)
- Test: `tests/poc/test_weekly.py`

**Interfaces:**
- Consumes: `run_synthesis`; `weekly.run` bundle output.
- Produces:
  - `synthesize.synthesize_bundle(bundle_dict: dict, prior_weekly: dict) -> dict` — orchestration wrapper: runs `run_synthesis`, writes `out/synthesis.json` + `out/synthesis_dropped.json`, returns status dict `{"claims": int, "dropped": int}` or `{"claims": 0, "fallback": str}` on LLM failure.
  - `synthesize._load_prior_weekly() -> dict` — build-phase stub returning `{}` (M4 seam; documented).
  - `weekly.run` calls `synthesize_bundle` after bundle write, adds `"synthesis"` to its return dict.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/poc/test_weekly.py — check existing imports/style first
def test_weekly_run_invokes_synthesis(monkeypatch, tmp_path):
    # 기존 test_weekly 패턴을 따를 것 — 축 스텁 방식은 현 파일 참고.
    # 핵심 단언: run() 결과에 "synthesis" 키가 있고 LLM 실패해도 번들은 살아남는다.
    import poc.weekly as weekly
    from poc import synthesize
    monkeypatch.setattr(synthesize, "run_synthesis",
                        lambda b, p: (_ for _ in ()).throw(RuntimeError("LLM 죽음")))
    # ... (기존 test가 naver/pinterest/extract_all/corpus.main을 어떻게 스텁하는지 그대로 재사용)
```

Read `tests/poc/test_weekly.py` first and mirror its existing stubbing of `corpus.main`, `naver.fetch_concept_trends`, `pinterest.fetch_categories`, `extract_all`. Assert: `"synthesis" in result` and that a synthesis LLM failure yields `result["synthesis"]["fallback"]` while `result["iso_week"]` still set (bundle survived).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/poc/test_weekly.py -q`
Expected: FAIL — `KeyError: 'synthesis'`

- [ ] **Step 3: Add `synthesize_bundle` + `_load_prior_weekly` + CLI**

Add to `poc/synthesize.py`:

```python
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
    import sys
    bundle_dict = json.loads((config.OUT_DIR / "merge_bundle.json").read_text(encoding="utf-8"))
    result = synthesize_bundle(bundle_dict, _load_prior_weekly())
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(exit_code(result))
```

Add `from poc import config` already present; ensure `import json` at top.

- [ ] **Step 4: Wire into `weekly.run`**

In `poc/weekly.py`, add import `from poc import synthesize` (extend existing `from poc import bundle, config, corpus, naver, pinterest`), then after the bundle files are written (after line 46) and before `return`:

```python
    synthesis_status = synthesize.synthesize_bundle(
        merged.model_dump(), synthesize._load_prior_weekly())
```

And add to the returned dict:

```python
        "synthesis": synthesis_status,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/poc/test_weekly.py tests/poc/test_synthesize.py -q`
Expected: PASS

- [ ] **Step 6: Full suite**

Run: `python3 -m pytest -q`
Expected: PASS (189 + new)

- [ ] **Step 7: Commit**

```bash
git add poc/weekly.py poc/synthesize.py tests/poc/test_weekly.py
git commit -m "feat(poc): M3 weekly 배선 — 번들 후 LLM#2 합성 단계 + CLI (SPEC_V3 §5.2, §8)"
```

- [ ] **Step 8: LIVE-VERIFY (acceptance §12 M3 — required, not unit-testable)**

Requires `ANTHROPIC_API_KEY` in `.env` and a real `out/merge_bundle.json`. Two paths:
- If a live bundle exists (run `python3 -m poc.weekly` first, or copy from main checkout `out/merge_bundle.json`), run: `python3 -m poc.synthesize`
- Expected: prints `{"claims": N, "dropped": M}` with N ≥ 1; `out/synthesis.json` contains claims each with `classification` ∈ {validated,leading,fading}, non-empty `evidence_refs`, and numbers matching the bundle. Confirm at least one classification present and validator dropped nothing spurious. **This is the acceptance gate** — green unit tests can mask runtime FAIL (§13). Report the live output to the owner.

---

## Notes for the implementer

- **M4 seam:** `_load_prior_weekly()` returns `{}` until M4 lands. When M4 merges, replace its body with `driver.get_prior_weeks`-backed lookup; the `{concept_id: {...}}` contract is fixed. No other M3 code changes.
- **weekly.py rebase:** synth is one call at the tail of `run()`; if M4 merges first, re-apply that single call after M4's storage call. Both are independent tail steps.
- **Do not** reproduce the full V2 §8.9 `Claim` yaml — this PoC uses the pragmatic `ConceptClaim` (traceable evidence + numeric cross-check fields), matching `poc/analyze.py`'s existing lighter Claim shape. Full FactRef machinery is YAGNI here.
