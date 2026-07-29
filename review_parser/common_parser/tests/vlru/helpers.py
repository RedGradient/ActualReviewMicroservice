from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from requests import Response

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_json(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


def vlru_thread_first_page() -> dict:
    """Первый ответ thread API (company=trinity)."""
    return _load_json("vlru_thread_first_page.json")


def vlru_comments_second_page() -> dict:
    """Вторая страница comments API для thread trinity."""
    return _load_json("vlru_comments_second_page.json")


def vlru_thread_last_page() -> dict:
    """Пустая страница — конец пагинации."""
    return _load_json("vlru_thread_last_page.json")


def vlru_avg_history() -> dict:
    """История средней оценки компании trinity (companyId=27297)."""
    return _load_json("vlru_avg_history.json")


def vlru_avg_history_low() -> dict:
    """История с низкой оценкой (< 4) для проверки clamp."""
    return _load_json("vlru_avg_history_low.json")


def vlru_comments_single_html() -> str:
    """Фрагмент HTML с одним отзывом из trinity."""
    return (_FIXTURES_DIR / "vlru_comments_single.html").read_text(encoding="utf-8")


def vlru_company_main_page_html() -> str:
    """Полная HTML главной страницы компании trinity."""
    return (_FIXTURES_DIR / "vlru_company_main_page.html").read_text(encoding="utf-8")


def make_response(text: str, *, status_code: int = 200) -> Response:
    response = Mock(spec=Response)
    response.status_code = status_code
    response.text = text
    response.raise_for_status = Mock()
    return response


def make_json_response(payload: dict[str, Any] | str, *, status_code: int = 200) -> Response:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    response = make_response(text, status_code=status_code)
    response.json = Mock(return_value=json.loads(text))
    return response


class FakeVLClient:
    """Fake VLClient: заранее заданные ответы + история вызовов."""

    def __init__(
        self,
        *,
        thread_payload: dict[str, Any] | None = None,
        comment_pages: list[dict[str, Any]] | None = None,
        avg_history_payload: dict[str, Any] | None = None,
    ):
        self.thread_payload = thread_payload
        self.comment_pages = list(comment_pages or [])
        self.avg_history_payload = avg_history_payload
        self.thread_calls: list[str] = []
        self.comments_calls: list[tuple[str, int | str, int | str]] = []
        self.avg_calls: list[int | str] = []
        self.company_pages_calls: list[str] = []

    def get_thread(self, company: str) -> Response:
        self.thread_calls.append(company)
        if self.thread_payload is None:
            raise AssertionError("thread_payload is not configured")
        return make_json_response(self.thread_payload)

    def get_comments_page(
        self,
        company: str,
        thread_id: int | str,
        before: int | str,
    ) -> Response:
        self.comments_calls.append((company, thread_id, before))
        if not self.comment_pages:
            raise AssertionError("comment_pages exhausted")
        return make_json_response(self.comment_pages.pop(0))

    def get_avg_history(self, company_id: int | str) -> Response:
        self.avg_calls.append(company_id)
        if self.avg_history_payload is None:
            raise AssertionError("avg_history_payload is not configured")
        return make_json_response(self.avg_history_payload)

    def get_company_page(self, company: str) -> Response:
        self.company_pages_calls.append(company)
        return make_response(vlru_company_main_page_html())
