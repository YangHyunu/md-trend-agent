"""Breuninger JSON-LD ItemList adapter 테스트. fixture는 2026-07-23 실 브랜드 리스팅 트리밍.

Breuninger 브랜드 리스팅(`/de/marken/iris-von-arnim/`)은 `application/ld+json`
ItemList(itemListElement→@type=Product)로 상품을 노출한다. 필드는 name·offers(price/
currency)·url(상대)·image 뿐 — brand·color·variant·availability는 없다(JSON-LD 한계,
정직 갭). item/materials는 name에서 추출(영문 어휘라 독일어 Mütze/Schal은 미매칭 None).
"""
from pathlib import Path

import httpx

from datalayer.sources.breuninger import BreuningerSource

_FIXTURE = (Path(__file__).parent / "fixtures" / "breuninger_iris.html").read_text()
_LISTING = "https://www.breuninger.com/de/marken/iris-von-arnim/"


def breuninger_client(path: str = "/de/marken/iris-von-arnim/") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path:
            return httpx.Response(200, text=_FIXTURE)
        return httpx.Response(404, text="Not Found")
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="https://www.breuninger.com")


def test_breuninger_fetch_maps_itemlist():
    with breuninger_client() as c:
        recs = BreuningerSource().fetch("Iris Von Arnim", _LISTING, c)
    assert recs is not None and len(recs) == 3
    pull = recs[1]
    assert pull.brand == "Iris Von Arnim"              # JSON-LD엔 brand 없음 → 인자값
    assert pull.item == "Sweater"                      # "Pullover" → Sweater
    assert pull.price_native == 1095.0
    assert pull.currency == "EUR"
    assert "cashmere" in pull.materials
    assert pull.source == "breuninger"
    # 상대 url → origin 붙여 절대화
    assert pull.url == ("https://www.breuninger.com/de/marken/iris-von-arnim/"
                        "cashmere-pullover-fallou-mit-3-4-arm/1002970597/p/")
    assert pull.image_url.startswith("https://cms.brnstc.de/")


def test_breuninger_unmatched_german_item_is_none():
    # 독일어 Mütze(beanie)·Schal(scarf)는 영문 item 어휘 미매칭 → None (정직 갭)
    with breuninger_client() as c:
        recs = BreuningerSource().fetch("Iris Von Arnim", _LISTING, c)
    muetze, schal = recs[0], recs[2]
    assert muetze.item is None and muetze.price_native == 325.0
    assert schal.item is None and "cashmere" in schal.materials


def test_breuninger_no_variant_detail_leaves_availability_unknown():
    # ItemList엔 색상·variant·availability 없음 — 단일 variant, available None
    with breuninger_client() as c:
        recs = BreuningerSource().fetch("Iris Von Arnim", _LISTING, c)
    p = recs[1]
    assert len(p.variants) == 1
    assert p.variants[0].available is None
    assert p.colors_raw == []
    assert p.on_sale is False and p.compare_at_native is None


def test_breuninger_returns_none_without_itemlist():
    def handler(request):
        return httpx.Response(200, text="<html><body>no ld+json</body></html>")
    with httpx.Client(transport=httpx.MockTransport(handler),
                      base_url="https://shop.test") as c:
        assert BreuningerSource().fetch("x", "https://shop.test/", c) is None
