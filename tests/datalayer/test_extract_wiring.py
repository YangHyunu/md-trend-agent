"""per-brand 소스 배선(sources_for) 테스트. owner 모델: 사다리 유지 + per-source primary.

미등록 브랜드는 기본 사다리(Shopify). 등록 브랜드는 지정 소스 + (필요시) URL override.
Breuninger의 ItemList 탐지는 generic이라 blind 사다리에 넣으면 LE17/COS 공식몰을
오매칭할 수 있어 per-brand 배선으로 격리한다.
"""
from datalayer.extract import sources_for
from datalayer.sources.breuninger import BreuningerSource
from datalayer.sources.kolonmall import KolonmallSource
from datalayer.sources.quince import QuinceSource
from datalayer.sources.shopify import ShopifySource


def test_unregistered_brand_uses_default_shopify_ladder():
    srcs, url = sources_for("Arch4")
    assert [type(s) for s in srcs] == [ShopifySource]
    assert url is None                                 # config url 사용


def test_quince_brand_uses_quince_source():
    srcs, url = sources_for("Quince")
    assert [type(s) for s in srcs] == [QuinceSource]
    assert url is None


def test_plushmere_brand_uses_kolonmall_source():
    srcs, url = sources_for("PLUSH'MERE")
    assert [type(s) for s in srcs] == [KolonmallSource]
    assert url is None                                 # config url이 코오롱몰 브랜드페이지


def test_iris_uses_breuninger_with_url_override():
    srcs, url = sources_for("Iris Von Arnim")
    assert [type(s) for s in srcs] == [BreuningerSource]
    # config url(irisvonarnim.com)이 아니라 Breuninger 리스팅으로 override
    assert url == "https://www.breuninger.com/de/marken/iris-von-arnim/"
