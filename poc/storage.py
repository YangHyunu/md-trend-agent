"""저장 계층 (SPEC_V3 §9) — 3테이블 sqlite driver + 주간 델타 + weekly 배선.

driver 인터페이스만 SPEC 규정(§9.3): put_article / upsert_concept / append_weekly /
get_prior_weeks / similar_concepts. 백엔드는 driver 뒤 — 1차 sqlite(파일 1개),
배포 전환 시 pgvector(스키마 동일, 벡터=컬럼 1개). RAG/GraphRAG 미채택(§9.3, §14).

멱등(§12 M4 수용 기준): articles url UNIQUE, concept_weekly PK(concept_id, iso_week).
동일 주 재실행은 upsert로 덮어써 결과가 동일하다.
"""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from poc import config
from poc.bundle import MergeBundle
from poc.measure import series_delta

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  id            TEXT PRIMARY KEY,
  source        TEXT,
  url           TEXT UNIQUE,
  title         TEXT,
  published_at  TEXT,
  fetched_at    TEXT,
  matched_terms TEXT,
  excerpt       TEXT,
  raw_path      TEXT
);
CREATE TABLE IF NOT EXISTS concepts (
  id              TEXT PRIMARY KEY,
  label_ko        TEXT,
  label_en        TEXT,
  aliases         TEXT,
  category        TEXT,
  first_seen_week TEXT,
  status          TEXT,
  source_refs     TEXT
);
CREATE TABLE IF NOT EXISTS concept_weekly (
  concept_id      TEXT,
  iso_week        TEXT,
  naver_series    TEXT,
  direction       TEXT,
  delta_pct       REAL,
  supply_count    INTEGER,
  editorial_count INTEGER,
  classification  TEXT,
  run_id          TEXT,
  PRIMARY KEY (concept_id, iso_week)
);
"""


def concept_id(label_ko: str) -> str:
    """concepts.json엔 id 부재 — label_ko 해시로 주간 안정 id 파생(시계열 누적 키)."""
    return "c" + hashlib.sha1(label_ko.encode()).hexdigest()[:10]


def weekly_delta(measurement: dict, prior_weeks: list[dict]) -> dict:
    """concept_weekly.direction/delta_pct 산출 (SPEC_V3 §9.2).

    첫 주(prior 없음): NAVER 시계열 자체 기울기(series_delta) 그대로.
    다음 주부터: 저장된 직전 주 recent_mean 대비 delta. 소량 베이스(<SMALL_BASE_MEAN)
    는 △ 캡(퍼센트 과장 금지). naver 축 부재는 insufficient — 0%로 표현하지 않는다.
    """
    naver = measurement.get("naver")
    if not naver:
        return {"direction": "insufficient", "delta_pct": None}
    if not prior_weeks:
        d = series_delta(naver["series"])
        return {"direction": d["direction"], "delta_pct": d["delta_pct"]}

    curr_mean = series_delta(naver["series"])["recent_mean"]
    prior_series = json.loads(prior_weeks[0]["naver_series"] or "[]")
    prior_mean = series_delta(prior_series)["recent_mean"]
    if curr_mean is None or prior_mean is None:
        return {"direction": "insufficient", "delta_pct": None}
    if prior_mean < config.SMALL_BASE_MEAN:
        return {"direction": "small_base", "delta_pct": None}
    delta = (curr_mean / prior_mean - 1) * 100
    if delta >= config.DELTA_FLAT_BAND_PCT:
        direction = "up"
    elif delta <= -config.DELTA_FLAT_BAND_PCT:
        direction = "down"
    else:
        direction = "flat"
    return {"direction": direction, "delta_pct": round(delta, 1)}


class SqliteDriver:
    """§9.3 driver — sqlite 백엔드. 스키마·인터페이스는 pgvector와 동일 설계."""

    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def put_article(self, article: dict) -> None:
        """url UNIQUE로 dedup — 재수집 멱등(ON CONFLICT DO NOTHING)."""
        self.conn.execute(
            """INSERT INTO articles
               (id, source, url, title, published_at, fetched_at,
                matched_terms, excerpt, raw_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(url) DO NOTHING""",
            (article["id"], article.get("source"), article["url"],
             article.get("title"), article.get("published_at"),
             article.get("fetched_at"),
             json.dumps(article.get("matched_terms", []), ensure_ascii=False),
             article.get("excerpt"), article.get("raw_path")),
        )
        self.conn.commit()

    def upsert_concept(self, concept: dict, iso_week: str) -> str:
        """id 반환. 최초 관측 주(first_seen_week)는 보존, 나머지 메타는 갱신."""
        cid = concept_id(concept["label_ko"])
        self.conn.execute(
            """INSERT INTO concepts
               (id, label_ko, label_en, aliases, category,
                first_seen_week, status, source_refs)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
               ON CONFLICT(id) DO UPDATE SET
                 label_en    = excluded.label_en,
                 aliases     = excluded.aliases,
                 category    = excluded.category,
                 status      = excluded.status,
                 source_refs = excluded.source_refs""",
            (cid, concept["label_ko"], concept.get("label_en"),
             json.dumps(concept.get("aliases", []), ensure_ascii=False),
             concept.get("category"), iso_week,
             json.dumps(concept.get("source_refs", []), ensure_ascii=False)),
        )
        self.conn.commit()
        return cid

    def append_weekly(self, row: dict) -> None:
        """PK(concept_id, iso_week) upsert — 동일 주 재실행 멱등(§12)."""
        self.conn.execute(
            """INSERT INTO concept_weekly
               (concept_id, iso_week, naver_series, direction, delta_pct,
                supply_count, editorial_count, classification, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(concept_id, iso_week) DO UPDATE SET
                 naver_series    = excluded.naver_series,
                 direction       = excluded.direction,
                 delta_pct       = excluded.delta_pct,
                 supply_count    = excluded.supply_count,
                 editorial_count = excluded.editorial_count,
                 classification  = excluded.classification,
                 run_id          = excluded.run_id""",
            (row["concept_id"], row["iso_week"],
             json.dumps(row.get("naver_series"), ensure_ascii=False),
             row.get("direction"), row.get("delta_pct"),
             row.get("supply_count"), row.get("editorial_count"),
             row.get("classification"), row.get("run_id")),
        )
        self.conn.commit()

    def get_prior_weeks(self, concept_id: str, n: int) -> list[dict]:
        """직전 n주 concept_weekly 행 (iso_week 내림차순, 최근이 먼저)."""
        rows = self.conn.execute(
            """SELECT * FROM concept_weekly
               WHERE concept_id = ?
               ORDER BY iso_week DESC LIMIT ?""",
            (concept_id, n),
        ).fetchall()
        return [dict(r) for r in rows]

    def similar_concepts(self, label: str) -> list[dict]:
        """개념 중복방지용 유사도 조회(§9.3) — 검색 증강 아님. MVP=토큰 겹침 LIKE.

        FTS5/sqlite-vec, 배포 시 pgvector는 동일 인터페이스 뒤 업그레이드로 지연.
        """
        tokens = [t for t in label.replace("-", " ").split() if t]
        if not tokens:
            return []
        clause = " OR ".join(
            "label_ko LIKE ? OR label_en LIKE ? OR aliases LIKE ?" for _ in tokens)
        params: list[str] = []
        for t in tokens:
            params += [f"%{t}%", f"%{t}%", f"%{t}%"]
        rows = self.conn.execute(
            f"SELECT * FROM concepts WHERE {clause}", params).fetchall()
        return [dict(r) for r in rows]


def store_bundle(bundle: MergeBundle, articles: list[dict],
                 driver: SqliteDriver, *, run_id: str) -> dict:
    """번들 → 3테이블 저장. weekly.run이 번들 산출 후 호출(§43 독립 함수)."""
    for a in articles:
        driver.put_article(a)

    week = bundle.iso_week
    for m in bundle.concepts:
        measurement = m.model_dump()
        concept = measurement["concept"]
        cid = driver.upsert_concept(concept, week)
        # 현재 주 재실행 시 이미 저장된 이번 주 행이 최신이라 2개 조회 후 제외 —
        # 그래야 재실행에도 델타 기준이 직전 주로 안정(§12 멱등).
        prior = [w for w in driver.get_prior_weeks(cid, 2) if w["iso_week"] != week][:1]
        delta = weekly_delta(measurement, prior)
        supply = measurement.get("supply")
        driver.append_weekly({
            "concept_id": cid,
            "iso_week": week,
            "naver_series": measurement["naver"]["series"] if measurement.get("naver") else None,
            "direction": delta["direction"],
            "delta_pct": delta["delta_pct"],
            "supply_count": supply["supply_count"] if supply else None,
            "editorial_count": measurement["editorial_count"],
            "classification": None,   # M3 claim 3분류 배선 대기 (§46)
            "run_id": run_id,
        })
    return {"articles": len(articles), "concepts": len(bundle.concepts)}


def persist(bundle: MergeBundle, articles: list[dict], *,
            now: datetime, db_path: Path | None = None) -> dict:
    """weekly.run 배선 진입점. run_id = iso_week + now 타임스탬프(결정론)."""
    db_path = db_path or config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = f"{bundle.iso_week}-{now.strftime('%Y%m%dT%H%M%SZ')}"
    with SqliteDriver(db_path) as driver:
        return store_bundle(bundle, articles, driver, run_id=run_id)
