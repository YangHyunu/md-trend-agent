from datalayer import extract
from tests.datalayer.fixtures import shopify_client, non_shopify_client


def test_extract_brand_via_shopify():
    with shopify_client() as c:
        res = extract.extract_brand("arch4", "https://shop.test/", client=c)
    assert res.source == "shopify"
    assert len(res.products) == 2
    assert res.failure is None


def test_extract_brand_non_shopify_records_failure():
    with non_shopify_client() as c:
        res = extract.extract_brand("cos", "https://shop.test/", client=c)
    assert res.source is None
    assert res.products == []
    assert res.failure  # 커버리지 갭 기록


def test_default_sources_only_shopify_for_now():
    names = [s.name for s in extract.default_sources()]
    assert names == ["shopify"]  # rung2-4는 플랜 #1b


def test_extract_all_skips_auto_collect_false():
    class B:
        def __init__(self, name, url, auto):
            self.name, self.url, self.auto_collect = name, url, auto

    brands = [B("a", "https://shop.test/", True), B("skip", "https://shop.test/", False)]
    with shopify_client() as c:
        results = extract.extract_all(brands, client=c)
    assert len(results) == 1
    assert results[0].brand == "a"
