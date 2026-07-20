from datalayer.ladder import run_ladder
from datalayer.records import ProductRecord


def _rec(brand):
    return ProductRecord(brand, "u", "Sweater", [], 1.0, "USD", None,
                         False, [], None, "shopify")


class _NoneSource:
    name = "sitemap"
    def fetch(self, brand, url, client):
        return None


class _OkSource:
    name = "shopify"
    def fetch(self, brand, url, client):
        return [_rec(brand)]


class _BoomSource:
    name = "render"
    def fetch(self, brand, url, client):
        raise RuntimeError("kaboom")


def test_ladder_takes_first_non_none_source():
    res = run_ladder("arch4", "https://x", [_NoneSource(), _OkSource()], client=None)
    assert res.source == "shopify"
    assert len(res.products) == 1
    assert res.failure is None


def test_ladder_all_none_records_failure_not_raise():
    res = run_ladder("quince", "https://x", [_NoneSource()], client=None)
    assert res.source is None
    assert res.products == []
    assert "지원 소스 없음" in res.failure


def test_ladder_captures_source_exception_and_continues():
    res = run_ladder("y", "https://x", [_BoomSource(), _OkSource()], client=None)
    assert res.source == "shopify"  # 예외 rung 건너뛰고 다음 성공


def test_ladder_all_fail_with_exception_records_error():
    res = run_ladder("y", "https://x", [_BoomSource()], client=None)
    assert res.source is None
    assert "render" in res.failure and "kaboom" in res.failure
