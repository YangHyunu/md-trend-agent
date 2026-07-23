"""소스 사다리 기본 배선. POC_SPEC §12.1/§12.2."""
import httpx

from datalayer.fields import LLMFn
from datalayer.ladder import run_ladder
from datalayer.records import BrandExtractionResult
from datalayer.sources.base import Source
from datalayer.sources.breuninger import BreuningerSource
from datalayer.sources.kolonmall import KolonmallSource
from datalayer.sources.quince import QuinceSource
from datalayer.sources.shopify import ShopifySource

DEFAULT_TIMEOUT = 30
# 정상 데스크톱 브라우저 신원 (§10.3 허용 — 차단 회피용 stealth 아님).
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def default_sources(llm_fn: LLMFn | None = None) -> list[Source]:
    """미등록 브랜드 기본 사다리. 현재 rung1(Shopify)만."""
    return [ShopifySource(llm_fn=llm_fn)]


# per-brand 소스 배선 (owner 모델: 사다리 유지 + per-source primary §9.1). 값은
# (소스리스트 팩토리, URL override|None). Breuninger의 ItemList 탐지가 generic이라
# blind 사다리에 못 넣고 per-brand로 격리한다. 미등록 브랜드는 default_sources.
_PER_BRAND: dict[str, tuple] = {
    "Quince": (lambda llm: [QuinceSource()], None),
    "PLUSH'MERE": (lambda llm: [KolonmallSource()], None),
    "Iris Von Arnim": (lambda llm: [BreuningerSource()],
                       "https://www.breuninger.com/de/marken/iris-von-arnim/"),
}


def sources_for(brand: str,
                llm_fn: LLMFn | None = None) -> tuple[list[Source], str | None]:
    """브랜드별 (소스 사다리, URL override). 미등록은 기본 Shopify 사다리."""
    entry = _PER_BRAND.get(brand)
    if entry is None:
        return default_sources(llm_fn), None
    factory, url = entry
    return factory(llm_fn), url


def _client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    return httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True,
                        headers={"User-Agent": _UA}), True


def extract_brand(brand: str, homepage_url: str, *,
                  llm_fn: LLMFn | None = None,
                  client: httpx.Client | None = None,
                  sources: list[Source] | None = None) -> BrandExtractionResult:
    c, own = _client(client)
    try:
        srcs = sources if sources is not None else default_sources(llm_fn)
        return run_ladder(brand, homepage_url, srcs, c)
    finally:
        if own:
            c.close()


def extract_all(brands, *, llm_fn: LLMFn | None = None,
                client: httpx.Client | None = None) -> list[BrandExtractionResult]:
    """auto_collect=True 브랜드만 순회, per-brand 소스 배선. 단일 client 재사용."""
    c, own = _client(client)
    try:
        results = []
        for b in brands:
            if not getattr(b, "auto_collect", True):
                continue
            srcs, url_override = sources_for(b.name, llm_fn)
            results.append(extract_brand(b.name, url_override or b.url,
                                         llm_fn=llm_fn, client=c, sources=srcs))
        return results
    finally:
        if own:
            c.close()
