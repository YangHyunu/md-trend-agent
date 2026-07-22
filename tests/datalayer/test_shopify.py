from datalayer.sources.shopify import ShopifySource
from tests.datalayer.fixtures import shopify_client, non_shopify_client


def test_shopify_fetch_maps_products():
    with shopify_client() as c:
        recs = ShopifySource().fetch("arch4", "https://shop.test/", c)
    assert recs is not None and len(recs) == 3
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
    assert cardigan.image_url == "https://cdn.shop.test/camel-cardigan-1.jpg"  # 첫 이미지
    assert recs[1].image_url is None                      # images 없는 상품


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


def test_shopify_preserves_all_variants_and_derives_metrics():
    # 멀티 variant 상품: 첫 variant만 쓰지 않고 min/max·세일비율·재고를 집계(§8.4)
    with shopify_client() as c:
        recs = ShopifySource().fetch("b", "https://shop.test/", c)
    jumper = recs[2]
    assert [v.variant_id for v in jumper.variants] == ["301", "302", "303"]
    assert jumper.price_min_native == 300.0 and jumper.price_max_native == 340.0
    assert jumper.price_native == 300.0                    # 대표가 = 최소가
    assert jumper.on_sale is True                          # 302가 세일
    assert jumper.sale_variant_ratio == round(1 / 3, 4)    # 3개 중 1개
    assert jumper.any_available is True and jumper.all_sold_out is False
    assert jumper.canonical_url == "https://shop.test/products/ribbed-jumper"


def test_shopify_returns_none_for_non_shopify():
    with non_shopify_client() as c:
        assert ShopifySource().fetch("cos", "https://shop.test/", c) is None
