from datetime import date

from datalayer.aggregate import brand_aggregate, _percentile
from datalayer.records import BrandExtractionResult, ProductRecord


def _p(price=None, cur="GBP", compare=None, sale=False, colors=None,
       item="Sweater", mats=None, pub=None, silhouettes=None):
    return ProductRecord(
        brand="b", url="u", item=item, colors_raw=colors or [],
        price_native=price, currency=cur, compare_at_native=compare,
        on_sale=sale, materials=mats or [], published_at=pub, source="shopify",
        silhouettes=silhouettes or [])


def test_percentile_linear_interpolation():
    vals = [10.0, 20.0, 30.0, 40.0]
    assert _percentile(vals, 0.5) == 25.0
    assert _percentile(vals, 0.0) == 10.0
    assert _percentile(vals, 1.0) == 40.0
    assert _percentile([], 0.5) is None
    assert _percentile([7.0], 0.5) == 7.0


def test_aggregate_empty_keeps_failure():
    r = BrandExtractionResult(brand="quince", source=None, products=[], failure="지원 소스 없음")
    agg = brand_aggregate(r)
    assert agg == {"brand": "quince", "source": None, "count": 0, "failure": "지원 소스 없음"}


def test_aggregate_computes_price_band_and_sale_ratio():
    prods = [_p(price=100.0, sale=False), _p(price=200.0, sale=True),
             _p(price=300.0, sale=True), _p(price=400.0, sale=False)]
    agg = brand_aggregate(BrandExtractionResult(brand="b", source="shopify", products=prods))
    assert agg["count"] == 4
    assert agg["currency"] == "GBP"
    assert agg["price"]["min"] == 100.0 and agg["price"]["max"] == 400.0
    assert agg["price"]["p50"] == 250.0
    assert agg["price"]["n"] == 4
    assert agg["sale_ratio"] == 0.5


def test_aggregate_price_skips_none_prices():
    prods = [_p(price=None), _p(price=150.0)]
    agg = brand_aggregate(BrandExtractionResult(brand="b", source="shopify", products=prods))
    assert agg["price"]["n"] == 1 and agg["price"]["min"] == 150.0


def test_aggregate_price_skips_zero_price_outliers():
    # 기프트카드/플레이스홀더 variant가 price=0으로 min을 왜곡하는 사례 (MDA-2)
    prods = [_p(price=0.0), _p(price=100.0), _p(price=200.0)]
    agg = brand_aggregate(BrandExtractionResult(brand="b", source="shopify", products=prods))
    assert agg["price"]["n"] == 2 and agg["price"]["min"] == 100.0


def test_aggregate_colors_items_materials_ranked_by_frequency():
    prods = [_p(colors=["Camel", "Grey"], item="Sweater", mats=["cashmere"]),
             _p(colors=["Camel"], item="Cardigan", mats=["cashmere", "wool"]),
             _p(colors=["Camel"], item="Sweater", mats=["cashmere"])]
    agg = brand_aggregate(BrandExtractionResult(brand="b", source="shopify", products=prods))
    assert agg["colors_top"][0] == ("Camel", 3)
    assert agg["items_top"][0] == ("Sweater", 2)
    assert agg["materials_top"][0] == ("cashmere", 3)


def test_aggregate_silhouettes_ranked_and_unmatched_counted():
    prods = [_p(silhouettes=["Relaxed", "Oversized"]),
             _p(silhouettes=["Relaxed"]),
             _p(silhouettes=[])]  # 실루엣 근거 없음 → unmatched
    agg = brand_aggregate(BrandExtractionResult(brand="b", source="shopify", products=prods))
    assert agg["silhouettes_top"][0] == ("Relaxed", 2)
    assert agg["silhouettes_unmatched"] == 1


def test_aggregate_newness_counts_within_window():
    # as_of 2026-07-20, 8주 컷오프 = 2026-05-25
    prods = [_p(pub="2026-07-01"), _p(pub="2026-06-10"), _p(pub="2026-01-01"), _p(pub=None)]
    agg = brand_aggregate(BrandExtractionResult(brand="b", source="shopify", products=prods),
                          as_of=date(2026, 7, 20))
    assert agg["newness"]["recent_count"] == 2   # 07-01, 06-10 (01-01 제외, None 제외)
    assert agg["newness"]["latest"] == "2026-07-01"
    assert agg["newness"]["weeks"] == 8
