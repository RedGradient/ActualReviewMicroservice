from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

from requests import Response


def make_response(text: str, *, status_code: int = 200) -> Response:
    response = Mock(spec=Response)
    response.status_code = status_code
    response.text = text
    response.json = Mock(return_value=json.loads(text))
    response.raise_for_status = Mock()
    return response


def make_json_response(payload: dict[str, Any] | str, *, status_code: int = 200) -> Response:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return make_response(text, status_code=status_code)


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
