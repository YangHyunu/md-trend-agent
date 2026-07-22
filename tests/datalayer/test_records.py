import pytest

from datalayer.records import (
    ProductRecord, BrandExtractionResult, Variant,
    canonical_url, derive_variant_metrics,
)


def test_product_record_holds_normalized_fields():
    r = ProductRecord(
        brand="arch4", url="https://www.arch4.co.uk/products/x",
        item="Sweater", colors_raw=["Camel"], price_native=240.0,
        currency="GBP", compare_at_native=625.0, on_sale=True,
        materials=["cashmere"], published_at="2026-06-01", source="shopify",
    )
    assert r.on_sale is True
    assert r.colors_raw == ["Camel"]
    assert r.currency == "GBP"


def test_brand_result_defaults_empty_and_no_failure():
    br = BrandExtractionResult(brand="quince", source=None)
    assert br.products == []
    assert br.failure is None
    assert br.source is None


def _v(vid, price, compare=None, available=None):
    return Variant(variant_id=vid, title=None, price_native=price,
                   compare_at_native=compare, available=available)


def test_canonical_url_strips_fragment_and_tracking_keeps_rest():
    u = canonical_url("https://x.com/p/a?utm_source=ig&color=camel&fbclid=z#frag")
    assert u == "https://x.com/p/a?color=camel"


def test_derive_metrics_min_max_sale_ratio_and_availability():
    m = derive_variant_metrics([
        _v("1", 300.0, 300.0, True),   # 세일 아님 (compare == price)
        _v("2", 320.0, 400.0, True),   # 세일
        _v("3", 340.0, None, False),
    ])
    assert m["price_min_native"] == 300.0 and m["price_max_native"] == 340.0
    assert m["any_variant_on_sale"] is True
    assert m["sale_variant_ratio"] == round(1 / 3, 4)
    assert m["any_available"] is True and m["all_sold_out"] is False


def test_derive_metrics_all_sold_out_only_when_all_false():
    m = derive_variant_metrics([_v("1", 100.0, None, False), _v("2", 120.0, None, False)])
    assert m["all_sold_out"] is True and m["any_available"] is False


def test_derive_metrics_availability_unknown_when_all_none():
    m = derive_variant_metrics([_v("1", 100.0), _v("2", 120.0)])
    assert m["any_available"] is None and m["all_sold_out"] is None


def _rec(**kw):
    base = dict(brand="b", url="https://x/p", item="Sweater", colors_raw=[],
                price_native=None, currency=None, compare_at_native=None,
                on_sale=False, materials=[], published_at=None, source="shopify")
    base.update(kw)
    return ProductRecord(**base)


def test_validate_rejects_empty_and_duplicate_variant_ids():
    with pytest.raises(ValueError):
        _rec(variants=[_v("", 10.0)]).validate()
    with pytest.raises(ValueError):
        _rec(variants=[_v("1", 10.0), _v("1", 20.0)]).validate()


def test_validate_rejects_price_min_gt_max_and_missing_currency():
    with pytest.raises(ValueError):
        _rec(price_min_native=500.0, price_max_native=100.0, currency="USD").validate()
    with pytest.raises(ValueError):
        _rec(price_min_native=100.0, currency=None).validate()  # 가격 있는데 통화 없음


def test_validate_passes_on_consistent_record():
    _rec(currency="USD", variants=[_v("1", 100.0, 120.0, True)],
         price_min_native=100.0, price_max_native=100.0,
         sale_variant_ratio=1.0).validate()
