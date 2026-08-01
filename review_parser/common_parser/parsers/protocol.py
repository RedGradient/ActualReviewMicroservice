from __future__ import annotations

from typing import Protocol

from common_parser.types import ParseResult


class ReviewParser(Protocol):
    provider: str

    def run(
        self,
        url: str,
        inn: str,
        *,
        org_name: str = "",
        address: str = "",
        limit: int = 50,
    ) -> ParseResult: ...

    def run_delay(
        self,
        url: str,
        inn: str,
        *,
        org_name: str = "",
        address: str = "",
    ) -> str: ...
