"""가짜 Shopify 몰 MockTransport. /products.json 페이지네이션 + /meta.json."""
import httpx

_PRODUCTS = [
    {  # 세일 상품, colour(British) 스펠링
        "handle": "camel-cardigan", "title": "Baby Cashmere Cardigan",
        "product_type": "Cardigan", "tags": ["knit", "cashmere"],
        "body_html": "<p>100% Cashmere</p>", "published_at": "2026-06-15T00:00:00Z",
        "options": [{"name": "Colour", "values": ["Camel", "Grey"]}],
        "variants": [{"price": "240.00", "compare_at_price": "625.00"}],
        "images": [{"src": "https://cdn.shop.test/camel-cardigan-1.jpg"},
                   {"src": "https://cdn.shop.test/camel-cardigan-2.jpg"}],
    },
    {  # product_type 비어있음 → 아이템 LLM 폴백 대상, color 옵션 없음
        "handle": "wool-scarf", "title": "Merino Scarf",
        "product_type": "", "tags": ["accessory"],
        "body_html": "<p>Merino wool, navy</p>", "published_at": "2026-05-01T00:00:00Z",
        "options": [{"name": "Title", "values": ["Default"]}],
        "variants": [{"price": "95.00", "compare_at_price": None}],
    },
]


def shopify_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/meta.json":
        return httpx.Response(200, json={"currency": "GBP"})
    if path == "/products.json":
        page = int(request.url.params.get("page", "1"))
        batch = _PRODUCTS if page == 1 else []
        return httpx.Response(200, json={"products": batch})
    return httpx.Response(404)


def shopify_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(shopify_handler),
                        base_url="https://shop.test")


def non_shopify_client() -> httpx.Client:
    def handler(request):
        return httpx.Response(404, text="Not Found")
    return httpx.Client(transport=httpx.MockTransport(handler))
