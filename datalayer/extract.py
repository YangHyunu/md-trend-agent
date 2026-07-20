"""소스 사다리 기본 배선. POC_SPEC §12.1/§12.2."""
import httpx

from datalayer.fields import LLMFn
from datalayer.ladder import run_ladder
from datalayer.records import BrandExtractionResult
from datalayer.sources.base import Source
from datalayer.sources.shopify import ShopifySource

DEFAULT_TIMEOUT = 30


def default_sources(llm_fn: LLMFn | None = None) -> list[Source]:
    """소스 사다리 rung 순서. 현재 rung1(Shopify)만 — rung2-4는 플랜 #1b."""
    return [ShopifySource(llm_fn=llm_fn)]


def _client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    return httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True), True


def extract_brand(brand: str, homepage_url: str, *,
                  llm_fn: LLMFn | None = None,
                  client: httpx.Client | None = None) -> BrandExtractionResult:
    c, own = _client(client)
    try:
        return run_ladder(brand, homepage_url, default_sources(llm_fn), c)
    finally:
        if own:
            c.close()


def extract_all(brands, *, llm_fn: LLMFn | None = None,
                client: httpx.Client | None = None) -> list[BrandExtractionResult]:
    """auto_collect=True 브랜드만 순회. 단일 client 재사용."""
    c, own = _client(client)
    try:
        results = []
        for b in brands:
            if not getattr(b, "auto_collect", True):
                continue
            results.append(extract_brand(b.name, b.url, llm_fn=llm_fn, client=c))
        return results
    finally:
        if own:
            c.close()
