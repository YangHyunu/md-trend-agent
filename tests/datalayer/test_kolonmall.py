"""코오롱몰 Apollo SSR transport adapter 테스트. fixture는 2026-07-23 실페이지 트리밍(§9.1).

코오롱몰은 Next.js App Router(RSC)지만 상품 데이터는 __next_f가 아니라 Apollo
SSRDataTransport 스크립트(plain JSON)에 있다. 컨테이너 __typename=products의
results[]/page를 파싱한다. 색상 단위 카드(색상별 code) — 리스트뷰는 style 묶음 없음.
"""
from pathlib import Path

import httpx
import pytest

from datalayer.sources.kolonmall import KolonmallSource, _price

_FIXTURE = (Path(__file__).parent / "fixtures" / "kolonmall_brand.html").read_text()
_HOME = "https://www.kolonmall.com/Brands/PLUSHMERE"


def kolon_client(path: str = "/Brands/PLUSHMERE") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path:
            return httpx.Response(200, text=_FIXTURE)
        return httpx.Response(404, text="Not Found")
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="https://www.kolonmall.com")


def test_kolonmall_fetch_maps_products():
    with kolon_client() as c:
        recs = KolonmallSource().fetch("PLUSH'MERE", _HOME, c)
    assert recs is not None and len(recs) == 3
    p0 = recs[0]
    assert p0.brand == "PLUSH'MERE"                     # supplierBrandName(플러쉬미어) 아님
    assert p0.item == "Top"                             # "... TOP" → Top
    assert p0.colors_raw == ["ORANGE"]
    assert p0.colors_family == ["옐로·오렌지"]
    assert p0.price_native == 72000.0
    assert p0.currency == "KRW"
    assert p0.source == "kolonmall"
    # code로 상품 URL 합성 (JSON에 url 필드 없음). 브랜드 경로는 homepage_url에서.
    assert p0.url == f"{_HOME}/Product/K1776313958789098OR01"
    assert p0.image_url.startswith("https://images.kolonmall.com/Prod_Img/")


def test_kolonmall_non_discounted_has_no_compare_at():
    # fixture 3건 전부 discountRate=0 → 가짜 세일가 방지: compare_at None, on_sale False
    with kolon_client() as c:
        recs = KolonmallSource().fetch("PLUSH'MERE", _HOME, c)
    assert all(r.compare_at_native is None for r in recs)
    assert all(r.on_sale is False for r in recs)


def test_kolonmall_variant_availability_from_soldout_flag():
    with kolon_client() as c:
        recs = KolonmallSource().fetch("PLUSH'MERE", _HOME, c)
    p0 = recs[0]
    # 색상 단위 단일 variant: code=variant_id, 색상명 title, soldOutYn=N → available
    assert [v.variant_id for v in p0.variants] == ["K1776313958789098OR01"]
    assert p0.variants[0].title == "ORANGE"
    assert p0.variants[0].available is True
    assert p0.any_available is True and p0.all_sold_out is False


def test_kolonmall_logs_ssr_cap_when_total_exceeds_collected(caplog):
    # page.totalCount=69 > 수집 3 → silent cap 금지, 경고 로그
    import logging
    with caplog.at_level(logging.WARNING), kolon_client() as c:
        KolonmallSource().fetch("PLUSH'MERE", _HOME, c)
    assert any("69" in r.message and "3" in r.message for r in caplog.records)


def test_kolonmall_returns_none_for_non_kolonmall():
    def handler(request):
        return httpx.Response(200, text="<html><body>no apollo transport</body></html>")
    with httpx.Client(transport=httpx.MockTransport(handler),
                      base_url="https://shop.test") as c:
        assert KolonmallSource().fetch("cos", "https://shop.test/", c) is None


# --- _price 순수함수: 할인 브랜치 (fixture엔 할인 상품 없어 단위테스트로 커버) ---

def test_price_no_discount_returns_none_compare():
    price, compare, on_sale = _price(
        {"price": 72000, "wishPrice": 72000, "discountRate": 0})
    assert price == 72000.0 and compare is None and on_sale is False


def test_price_with_discount_maps_wishprice_to_compare():
    price, compare, on_sale = _price(
        {"price": 100000, "wishPrice": 142200, "discountRate": 30})
    assert price == 100000.0 and compare == 142200.0 and on_sale is True


def test_price_missing_price_is_none():
    price, compare, on_sale = _price({"discountRate": 0})
    assert price is None and compare is None and on_sale is False
