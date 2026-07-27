from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple


@dataclass
class ReviewsBundle:
    reviews: list[dict[str, Any]]
    count: int | None
    rating: float | None


class ParseResult(NamedTuple):
    parsed: int
    created: int
