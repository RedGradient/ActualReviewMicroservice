from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from requests import Response

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def twogis_api_response() -> str:
    """Текст JSON-ответа 2GIS Reviews API (одна страница, один отзыв)."""
    return (_FIXTURES_DIR / "twogis_api_response.json").read_text(encoding="utf-8")


def make_response(text: str, *, status_code: int = 200) -> Response:
    response = Mock(spec=Response)
    response.status_code = status_code
    response.text = text
    response.raise_for_status = Mock()
    return response


def fake_get_reviews_page(response_text: str):
    """Возвращает callable для одной и той же страницы ответа."""

    def get_reviews_page(firm_id: str, limit: int, offset: int = 0) -> Response:
        return make_response(response_text)

    return get_reviews_page


def make_reviews_page(
    reviews: list[dict[str, Any]],
    *,
    rating: float = 4.8,
    count: int | None = None,
) -> dict[str, Any]:
    review_count = count if count is not None else len(reviews)
    return {
        "meta": {
            "branch_rating": rating,
            "branch_reviews_count": review_count,
            "total_count": review_count,
            "code": 200,
        },
        "reviews": reviews,
    }


class FakeGetReviews:
    """Fake для пагинации: несколько страниц + история вызовов."""

    def __init__(self, pages: list[str | dict[str, Any]]):
        self._pages = [
            page if isinstance(page, str) else json.dumps(page, ensure_ascii=False)
            for page in pages
        ]
        self.calls: list[tuple[str, int, int]] = []

    def __call__(self, firm_id: str, limit: int, offset: int = 0) -> Response:
        self.calls.append((firm_id, limit, offset))

        page_index = offset // limit if limit else 0
        if page_index < len(self._pages):
            text = self._pages[page_index]
        else:
            text = json.dumps(make_reviews_page([], count=0), ensure_ascii=False)

        return make_response(text)
