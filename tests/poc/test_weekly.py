"""weekly 오케스트레이션 테스트 — 축 실패 격리가 M2 수용 기준 (SPEC_V3 §12). LLM·네트워크 없음."""
import json
from datetime import datetime, timezone

from poc import config, weekly

NOW = datetime(2026, 7, 23, 3, 0, tzinfo=timezone.utc)

_CONCEPT = {"label_ko": "캐시미어 니트", "label_en": "cashmere knit", "aliases": [],
            "category": "소재", "naver_queries": ["캐시미어 니트"],
            "source_refs": ["a0000000001"], "rationale": "r"}


def _setup(monkeypatch, tmp_path, *, naver_raises: bool):
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    (tmp_path / "concepts.json").write_text(json.dumps([_CONCEPT], ensure_ascii=False))
    monkeypatch.setattr(weekly.corpus, "main",
                        lambda now=None: {"concepts": 1, "dropped": 0})

    def fake_naver(concepts):
        if naver_raises:
            raise RuntimeError("boom")
        return {"raw": {}, "signals": [], "failures": []}

    monkeypatch.setattr(weekly.naver, "fetch_concept_trends", fake_naver)
    monkeypatch.setattr(weekly.pinterest, "fetch_categories",
                        lambda: {"raw": {}, "signals": [], "failures": []})
    monkeypatch.setattr(weekly, "extract_all", lambda brands: [])


def test_weekly_writes_bundle_and_archive(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, naver_raises=False)
    summary = weekly.run(now=NOW)
    assert summary["iso_week"] == "2026-W30" and summary["concepts"] == 1
    latest = json.loads((tmp_path / "merge_bundle.json").read_text())
    archive = json.loads((tmp_path / "weekly" / "merge_bundle_2026-W30.json").read_text())
    assert latest["schema_version"] == "3.0"
    assert latest == archive


def test_weekly_axis_exception_is_isolated(monkeypatch, tmp_path):
    # M2 수용 기준: 축 1개가 raise해도 번들은 생성되고 실패가 coverage에 남는다
    _setup(monkeypatch, tmp_path, naver_raises=True)
    weekly.run(now=NOW)
    bundle = json.loads((tmp_path / "merge_bundle.json").read_text())
    assert bundle["concepts"][0]["naver"] is None
    assert any("boom" in f["error"]
               for f in bundle["coverage"]["naver"]["failures"])
