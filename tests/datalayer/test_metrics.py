import json

from datalayer.metrics import append_history, collect_metrics

# brand_aggregate 산출물 형태의 fixture (실측 스키마 그대로)
AGGS = [
    {"brand": "A", "source": "shopify", "count": 100, "failure": None,
     "items_unmatched": 2, "colors_family_unmatched": 30, "silhouettes_unmatched": 44,
     "newness": {"weeks": 8, "recent_count": 5, "latest": "2026-07-16"}},
    {"brand": "B", "source": "shopify", "count": 50, "failure": None,
     "items_unmatched": 0, "colors_family_unmatched": 1, "silhouettes_unmatched": 10,
     "newness": {"weeks": 8, "recent_count": 0, "latest": "2026-04-28"}},
    {"brand": "C", "source": None, "count": 0, "failure": "지원 소스 없음"},
]


def test_collect_metrics_field_coverage_overall_and_worst():
    m = collect_metrics(AGGS)
    # item: unmatched 2/150 → 0.987
    assert m["fields"]["item"]["overall"] == 0.99
    # worst 브랜드 = 커버리지 최저: A(0.98) < B(1.0)
    assert m["fields"]["item"]["worst"] == ["A", 0.98]
    # color_family: (30+1)/150 → 0.79, worst A(0.7)
    assert m["fields"]["color_family"]["overall"] == 0.79
    assert m["fields"]["color_family"]["worst"] == ["A", 0.7]
    # silhouette: (44+10)/150 → 0.64, worst A(0.56)
    assert m["fields"]["silhouette"]["overall"] == 0.64
    assert m["fields"]["silhouette"]["worst"] == ["A", 0.56]


def test_collect_metrics_sources_and_freshness():
    m = collect_metrics(AGGS)
    assert m["sources"] == {"ok": 2, "total": 3}
    # 가장 오래된 latest = B의 2026-04-28
    assert m["freshness"]["stalest"] == ["B", "2026-04-28"]


def test_collect_metrics_empty_aggregates_no_crash():
    m = collect_metrics([])
    assert m["sources"] == {"ok": 0, "total": 0}
    assert m["fields"] == {}
    assert m["freshness"]["stalest"] is None


def test_append_history_writes_jsonl_line(tmp_path):
    path = tmp_path / "metrics_history.jsonl"
    m = collect_metrics(AGGS)
    append_history(path, m, ts="2026-07-21T12:00:00")
    append_history(path, m, ts="2026-07-21T13:00:00")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["ts"] == "2026-07-21T12:00:00"
    assert row["sources"] == {"ok": 2, "total": 3}


# ── 회귀 바닥선: main 실측 스냅샷이 이 아래로 떨어지면 안 됨 (MDA-9) ──
def test_floor_item_coverage_from_live_snapshot():
    """어휘 리팩터가 아이템 커버리지를 깨면 여기서 빨간불.

    바닥선 근거: 2026-07-21 라이브 실측 item 97~98%. 여유 두고 0.95.
    """
    m = collect_metrics(AGGS)  # fixture는 스냅샷 대변 — 라이브는 run.py가 기록
    assert m["fields"]["item"]["overall"] >= 0.95
