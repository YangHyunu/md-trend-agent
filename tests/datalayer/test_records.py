from datalayer.records import ProductRecord, BrandExtractionResult


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
