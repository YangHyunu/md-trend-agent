"""라이브 스모크: python -m datalayer.smoke [브랜드명부분]
실제 몰에 붙어 추출 결과 요약 출력. 테스트 아님(네트워크 의존)."""
import sys

from poc import config
from datalayer.extract import extract_brand


def main() -> int:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    for b in config.BRANDS:
        if not b.auto_collect or (needle and needle not in b.name.lower()):
            continue
        res = extract_brand(b.name, b.url)
        if res.source is None:
            print(f"{b.name:20} source=None  FAIL: {res.failure[:80]}")
            continue
        n = len(res.products)
        with_price = sum(1 for p in res.products if p.price_native is not None)
        with_color = sum(1 for p in res.products if p.colors_raw)
        cur = res.products[0].currency if res.products else "?"
        print(f"{b.name:20} source={res.source} n={n} cur={cur} "
              f"price={with_price}/{n} color={with_color}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
