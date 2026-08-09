from __future__ import annotations

from common_parser.parsers.protocol import ReviewParser, VideoParser
from common_parser.parsers.twogis.parser import TwoGisParser
from common_parser.parsers.vlru.parser import VlruParser
from common_parser.parsers.yandex.parser import YandexMapParser
from common_parser.parsers.youtube.parser import YoutubeParser

REVIEW_PARSERS: list[ReviewParser] = [
    TwoGisParser(),
    VlruParser(),
    YandexMapParser(),
]

REVIEW_PARSERS_BY_PROVIDER: dict[str, ReviewParser] = {parser.provider: parser for parser in REVIEW_PARSERS}


VIDEO_PARSERS: list[VideoParser] = [
    YoutubeParser(),
]

VIDEO_PARSERS_BY_PROVIDER: dict[str, VideoParser] = {parser.provider: parser for parser in VIDEO_PARSERS}


def get_review_parser(provider: str) -> ReviewParser:
    try:
        return REVIEW_PARSERS_BY_PROVIDER[provider]
    except KeyError as exc:
        raise KeyError(f"Unknown review parser: {provider!r}") from exc


def get_video_parser(provider: str) -> VideoParser:
    try:
        return VIDEO_PARSERS_BY_PROVIDER[provider]
    except KeyError as exc:
        raise KeyError(f"Unknown video parser: {provider!r}") from exc
