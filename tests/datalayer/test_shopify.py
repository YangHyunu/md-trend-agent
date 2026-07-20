from datalayer.sources.shopify import ShopifySource
from tests.datalayer.fixtures import shopify_client, non_shopify_client


def test_shopify_fetch_maps_products():
    with shopify_client() as c:
        recs = ShopifySource().fetch("arch4", "https://shop.test/", c)
    assert recs is not None and len(recs) == 2
    cardigan = recs[0]
    assert cardigan.item == "Cardigan"
    assert cardigan.colors_raw == ["Camel", "Grey"]      # Colour 스펠링 인식
    assert (cardigan.price_native, cardigan.compare_at_native) == (240.0, 625.0)
    assert cardigan.on_sale is True
    assert cardigan.currency == "GBP"                     # meta.json
    assert "cashmere" in cardigan.materials
    assert cardigan.published_at == "2026-06-15"
    assert cardigan.url == "https://shop.test/products/camel-cardigan"
    assert cardigan.source == "shopify"


def test_shopify_item_llm_fallback_when_product_type_blank():
    with shopify_client() as c:
        recs = ShopifySource(llm_fn=lambda p: "Scarf").fetch("b", "https://shop.test/", c)
    scarf = recs[1]
    assert scarf.item == "Scarf"                          # product_type 빈값→LLM


def test_shopify_color_llm_fallback_verified_against_body():
    # scarf는 color 옵션 없음. LLM이 navy(body에 존재)·pink(없음) → navy만 채택
    with shopify_client() as c:
        recs = ShopifySource(llm_fn=lambda p: "navy, pink").fetch("b", "https://shop.test/", c)
    scarf = recs[1]
    assert scarf.colors_raw == ["navy"]


def test_shopify_returns_none_for_non_shopify():
    with non_shopify_client() as c:
        assert ShopifySource().fetch("cos", "https://shop.test/", c) is None
