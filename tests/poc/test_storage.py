"""저장 계층 테스트 (SPEC_V3 §9) — 결정론(§13). 네트워크·LLM 없음, tmp_path 파일 DB."""
import json
from datetime import datetime, timezone

from poc import storage
from poc.storage import SqliteDriver, concept_id, weekly_delta

NOW = datetime(2026, 7, 23, 3, 0, tzinfo=timezone.utc)


def _series(ratios: list[float]) -> list[dict]:
    return [{"period": f"2026-06-{i+1:02d}", "ratio": r} for i, r in enumerate(ratios)]


def _driver(tmp_path) -> SqliteDriver:
    return SqliteDriver(tmp_path / "t.db")


def _article(url: str, term: str = "cashmere") -> dict:
    return {"id": "a" + url[-3:], "source": "wwd:cashmere", "url": url,
            "title": "T", "published_at": None, "fetched_at": "2026-07-23T00:00:00+00:00",
            "matched_terms": [term], "excerpt": "e"}


def _concept(label_ko="캐시미어 니트", label_en="cashmere knit") -> dict:
    return {"label_ko": label_ko, "label_en": label_en, "aliases": ["니트"],
            "category": "소재", "naver_queries": [label_ko],
            "source_refs": ["a0000000001"], "rationale": "r"}


# --- put_article: url UNIQUE 멱등 ---

def test_put_article_dedups_by_url(tmp_path):
    d = _driver(tmp_path)
    d.put_article(_article("https://x.com/1"))
    d.put_article(_article("https://x.com/1"))   # 동일 url 재삽입
    rows = d.conn.execute("SELECT * FROM articles").fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0]["matched_terms"]) == ["cashmere"]
    assert rows[0]["raw_path"] is None   # articles.jsonl엔 raw_path 부재 → NULL


# --- upsert_concept: first_seen_week 보존 ---

def test_upsert_concept_preserves_first_seen_week(tmp_path):
    d = _driver(tmp_path)
    cid = d.upsert_concept(_concept(), "2026-W30")
    assert cid == concept_id("캐시미어 니트")
    d.upsert_concept(_concept(), "2026-W31")   # 다음 주 재관측
    row = d.conn.execute("SELECT * FROM concepts WHERE id=?", (cid,)).fetchone()
    assert row["first_seen_week"] == "2026-W30"   # 최초 관측 주 불변
    assert row["status"] == "active"


# --- append_weekly: PK 멱등 ---

def test_append_weekly_pk_idempotent(tmp_path):
    d = _driver(tmp_path)
    row = {"concept_id": "c1", "iso_week": "2026-W30", "naver_series": _series([1] * 8),
           "direction": "up", "delta_pct": 10.0, "supply_count": 3,
           "editorial_count": 2, "classification": None, "run_id": "r1"}
    d.append_weekly(row)
    d.append_weekly({**row, "direction": "down", "run_id": "r2"})   # 동일 (concept,week)
    rows = d.conn.execute("SELECT * FROM concept_weekly").fetchall()
    assert len(rows) == 1
    assert rows[0]["direction"] == "down" and rows[0]["run_id"] == "r2"   # 최신값 덮어씀


def test_get_prior_weeks_orders_recent_first(tmp_path):
    d = _driver(tmp_path)
    for wk in ["2026-W28", "2026-W29", "2026-W30"]:
        d.append_weekly({"concept_id": "c1", "iso_week": wk, "naver_series": [],
                         "direction": "flat", "delta_pct": None, "supply_count": None,
                         "editorial_count": 0, "classification": None, "run_id": "r"})
    prior = d.get_prior_weeks("c1", 2)
    assert [p["iso_week"] for p in prior] == ["2026-W30", "2026-W29"]


# --- weekly_delta: §9.2 규칙 ---

def test_weekly_delta_first_week_uses_series_slope(tmp_path):
    m = {"naver": {"series": _series([10, 10, 10, 10, 20, 20, 20, 20])}}
    assert weekly_delta(m, []) == {"direction": "up", "delta_pct": 100.0}


def test_weekly_delta_subsequent_week_vs_prior_recent_mean(tmp_path):
    m = {"naver": {"series": _series([0, 0, 0, 0, 40, 40, 40, 40])}}   # recent_mean 40
    prior = [{"naver_series": json.dumps(_series([0, 0, 0, 0, 20, 20, 20, 20])),  # recent_mean 20
              "iso_week": "2026-W29"}]
    assert weekly_delta(m, prior) == {"direction": "up", "delta_pct": 100.0}


def test_weekly_delta_prior_small_base_caps(tmp_path):
    m = {"naver": {"series": _series([0, 0, 0, 0, 40, 40, 40, 40])}}
    prior = [{"naver_series": json.dumps(_series([0, 0, 0, 0, 2, 2, 2, 2])),  # recent_mean 2 < 3
              "iso_week": "2026-W29"}]
    assert weekly_delta(m, prior) == {"direction": "small_base", "delta_pct": None}


def test_weekly_delta_no_naver_is_insufficient(tmp_path):
    assert weekly_delta({"naver": None}, []) == {"direction": "insufficient", "delta_pct": None}


# --- similar_concepts: 토큰 겹침 ---

def test_similar_concepts_token_overlap(tmp_path):
    d = _driver(tmp_path)
    d.upsert_concept(_concept("포인텔 니트", "pointelle knit"), "2026-W30")
    d.upsert_concept(_concept("크롭 가디건", "crop cardigan"), "2026-W30")
    hits = d.similar_concepts("pointelle top")
    assert [h["label_ko"] for h in hits] == ["포인텔 니트"]


# --- store_bundle / persist: end-to-end 2주 델타 + 멱등 (§12 수용 기준) ---

def _bundle(iso_week: str, series: list[dict]):
    from poc.bundle import ConceptMeasurement, MergeBundle, NaverMeasure, SupplyMeasure
    naver = NaverMeasure(series=series, delta_pct=None, direction="up",
                         recent_mean=None, prior_mean=None)
    supply = SupplyMeasure(supply_count=5, facets={}, unmeasurable=False)
    cm = ConceptMeasurement(concept=_concept(), naver=naver, supply=supply, editorial_count=3)
    return MergeBundle(iso_week=iso_week, generated_at=NOW.isoformat(),
                       concepts=[cm], pinterest_category=[], supply_brands=[], coverage={})


def test_persist_two_weeks_produces_delta(tmp_path):
    db = tmp_path / "trend.db"
    arts = [_article("https://x.com/1"), _article("https://x.com/2")]
    storage.persist(_bundle("2026-W29", _series([0, 0, 0, 0, 20, 20, 20, 20])),
                    arts, now=NOW, db_path=db)
    storage.persist(_bundle("2026-W30", _series([0, 0, 0, 0, 40, 40, 40, 40])),
                    arts, now=NOW, db_path=db)
    d = SqliteDriver(db)
    cid = concept_id("캐시미어 니트")
    w30 = d.conn.execute(
        "SELECT * FROM concept_weekly WHERE concept_id=? AND iso_week=?",
        (cid, "2026-W30")).fetchone()
    assert w30["direction"] == "up" and w30["delta_pct"] == 100.0   # W29 대비
    assert w30["supply_count"] == 5 and w30["editorial_count"] == 3
    assert w30["classification"] is None   # M3 배선 대기
    assert d.conn.execute("SELECT COUNT(*) c FROM articles").fetchone()["c"] == 2


def test_persist_rerun_keeps_delta_vs_prior_week(tmp_path):
    # 재실행 시 이미 저장된 이번 주 행을 직전 주로 오인하면 델타가 series-slope로 뒤집힌다
    db = tmp_path / "trend.db"
    arts = [_article("https://x.com/1")]
    storage.persist(_bundle("2026-W29", _series([0, 0, 0, 0, 20, 20, 20, 20])),
                    arts, now=NOW, db_path=db)
    b30 = _bundle("2026-W30", _series([0, 0, 0, 0, 40, 40, 40, 40]))
    storage.persist(b30, arts, now=NOW, db_path=db)
    storage.persist(b30, arts, now=NOW, db_path=db)   # W30 재실행
    d = SqliteDriver(db)
    w30 = d.conn.execute(
        "SELECT * FROM concept_weekly WHERE concept_id=? AND iso_week=?",
        (concept_id("캐시미어 니트"), "2026-W30")).fetchone()
    assert w30["direction"] == "up" and w30["delta_pct"] == 100.0   # W29 기준 유지


def test_persist_same_week_rerun_idempotent(tmp_path):
    db = tmp_path / "trend.db"
    arts = [_article("https://x.com/1")]
    b = _bundle("2026-W30", _series([1] * 8))
    storage.persist(b, arts, now=NOW, db_path=db)
    storage.persist(b, arts, now=NOW, db_path=db)   # 동일 주 재실행
    d = SqliteDriver(db)
    assert d.conn.execute("SELECT COUNT(*) c FROM concept_weekly").fetchone()["c"] == 1
    assert d.conn.execute("SELECT COUNT(*) c FROM articles").fetchone()["c"] == 1
    assert d.conn.execute("SELECT COUNT(*) c FROM concepts").fetchone()["c"] == 1
