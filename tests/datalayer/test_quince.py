"""Quince CLP __NEXT_DATA__ adapter 테스트. fixture는 2026-07-23 실페이지 트리밍(§24.2)."""
from pathlib import Path

import httpx

from datalayer.sources.quince import QuinceSource

_FIXTURE = (Path(__file__).parent / "fixtures" / "quince_clp.html").read_text()


def quince_client(paths: tuple[str, ...] = ("/shop/women/cashmere",)) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in paths:
            return httpx.Response(200, text=_FIXTURE)
        return httpx.Response(404, text="Not Found")
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="https://www.quince.com")


def test_quince_fetch_maps_products():
    with quince_client() as c:
        recs = QuinceSource().fetch("Quince", "https://www.quince.com/", c)
    assert recs is not None and len(recs) == 3
    tee = recs[0]
    assert tee.item == "Sweater"                      # class "Crewneck" → Sweater
    assert tee.colors_raw == ["Rich Burgundy", "Ivory", "Pale Custard Yellow"]
    assert tee.price_native == 44.9                    # 대표가 = variant 최소가
    assert tee.price_min_native == 44.9 and tee.price_max_native == 49.9
    assert tee.currency == "USD"
    assert tee.compare_at_native is None               # Quince 상시가 — 세일 신호 없음
    assert tee.on_sale is False
    assert "cashmere" in tee.materials
    assert tee.url == "https://www.quince.com/women/cashmere/cashmere-tee-shirt"
    assert tee.canonical_url == "https://www.quince.com/women/cashmere/cashmere-tee-shirt"
    assert tee.source == "quince_next"
    assert tee.image_url.startswith("https://images.ctfassets.net/")  # //-상대경로 보정


def test_quince_item_falls_back_class_then_department_then_title():
    with quince_client() as c:
        recs = QuinceSource().fetch("Quince", "https://www.quince.com/", c)
    scarf, cardigan = recs[1], recs[2]
    assert scarf.item == "Scarf"                       # dept "Soft Accessories" 미매칭 → class
    assert cardigan.item == "Cardigan"                 # class "Cardigan" 우선 (dept는 Sweater)


def test_quince_variant_availability_from_card_tags():
    with quince_client() as c:
        recs = QuinceSource().fetch("Quince", "https://www.quince.com/", c)
    tee, scarf = recs[0], recs[1]
    # 색상 단위 variant 보존: variantId·색상명·가격
    assert [v.variant_id for v in tee.variants] == ["74606", "3459", "122521"]
    assert tee.variants[0].title == "Rich Burgundy"
    # "Sold Out" 태그만 품절, Low Stock·무태그는 구매 가능
    assert [v.available for v in scarf.variants] == [False, True]
    assert scarf.any_available is True and scarf.all_sold_out is False
    assert tee.any_available is True


def test_quince_dedupes_products_across_collection_paths():
    paths = ("/shop/women/cashmere", "/shop/women/sweaters")
    with quince_client(paths) as c:
        recs = QuinceSource(collection_paths=[p.lstrip("/") for p in paths]).fetch(
            "Quince", "https://www.quince.com/", c)
    assert len(recs) == 3                              # 동일 productId 중복 제거


def test_quince_returns_none_for_non_quince():
    def handler(request):
        return httpx.Response(200, text="<html><body>no next data</body></html>")
    with httpx.Client(transport=httpx.MockTransport(handler),
                      base_url="https://shop.test") as c:
        assert QuinceSource().fetch("cos", "https://shop.test/", c) is None


def test_default_paths_are_subcollection_union():
    # 2026-07-23 실측: SSR은 페이지네이션 쿼리 무시 → sitemap 하위 컬렉션 유니온이 유일한 커버리지 경로
    from datalayer.sources.quince import _DEFAULT_PATHS
    assert _DEFAULT_PATHS[0] == "shop/women/cashmere"          # 루트 유지
    assert len(_DEFAULT_PATHS) == 12
    assert len(set(_DEFAULT_PATHS)) == 12                       # 중복 없음
    assert "shop/women/sweaters-&-jackets/cashmere" in _DEFAULT_PATHS


def test_default_paths_survive_dead_subcollections():
    # 하위 컬렉션이 404로 죽어도(사이트 개편) 루트만 살아있으면 수집은 성공해야 한다
    with quince_client() as c:   # 핸들러는 루트만 200, 나머지 404
        recs = QuinceSource().fetch("Quince", "https://www.quince.com/", c)
    assert recs is not None and len(recs) == 3
