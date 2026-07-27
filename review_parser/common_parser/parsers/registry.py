from __future__ import annotations

from common_parser.parsers.protocol import ReviewParser
from twogis_parser.tools.parser import TwoGisParser
from vl_parser.tools.parser import VlruParser

REVIEW_PARSERS: list[ReviewParser] = [
    TwoGisParser(),
    VlruParser(),
]

REVIEW_PARSERS_BY_PROVIDER: dict[str, ReviewParser] = {
    parser.provider: parser for parser in REVIEW_PARSERS
}


def get_review_parser(provider: str) -> ReviewParser:
    try:
        return REVIEW_PARSERS_BY_PROVIDER[provider]
    except KeyError as exc:
        raise KeyError(f"Unknown review parser: {provider!r}") from exc
