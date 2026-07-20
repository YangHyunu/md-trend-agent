"""소스 사다리 rung 인터페이스."""
from typing import Protocol

import httpx

from datalayer.records import ProductRecord


class Source(Protocol):
    name: str

    def fetch(self, brand: str, homepage_url: str,
              client: httpx.Client) -> list[ProductRecord] | None:
        """이 소스로 처리 가능하면 ProductRecord 리스트, 불가하면 None."""
        ...
