"""Shopify 429 local_rate_limited 백오프 재시도. sleep은 주입해 테스트 즉시 실행."""
import httpx

from datalayer.sources import shopify


def _client_seq(statuses: list[int]) -> httpx.Client:
    """호출마다 statuses를 순서대로 반환하는 MockTransport."""
    calls = {"n": 0}

    def handler(request):
        i = min(calls["n"], len(statuses) - 1)
        calls["n"] += 1
        st = statuses[i]
        if st == 200:
            return httpx.Response(200, json={"products": []})
        return httpx.Response(429, text="local_rate_limited")

    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="https://shop.test")


def test_get_retries_on_429_then_succeeds():
    slept = []
    with _client_seq([429, 429, 200]) as c:
        r = shopify._get(c, "/products.json", {"limit": 1},
                         retries=4, sleep_fn=slept.append)
    assert r.status_code == 200
    assert len(slept) == 2                      # 두 번 백오프 후 성공
    assert slept[1] > slept[0]                  # 지수 백오프


def test_get_gives_up_after_retries_returns_last_429():
    slept = []
    with _client_seq([429]) as c:
        r = shopify._get(c, "/products.json", {"limit": 1},
                         retries=3, sleep_fn=slept.append)
    assert r.status_code == 429                 # 소진 후 마지막 429 반환
    assert len(slept) == 3
