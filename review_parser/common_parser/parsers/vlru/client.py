from __future__ import annotations

from collections.abc import Callable

from requests import Response

from common_parser.services.http_client import get as http_get


class VLClient:
    """HTTP-клиент VL.ru Comments API."""

    def __init__(self, http_get_fn: HttpGet = http_get):
        self._http_get = http_get_fn

    @staticmethod
    def _ajax_headers(*, referer: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def get_thread(self, company: str) -> Response:
        url = f"https://www.vl.ru/commentsgate/ajax/thread/company/{company}/embedded"
        return self._http_get(
            url,
            headers=self._ajax_headers(referer=f"https://www.vl.ru/{company}"),
            params={"theme": "company", "moderatorMode": "1"},
        )

    def get_comments_page(self, company: str, thread_id: int | str, before: int | str) -> Response:
        url = f"https://www.vl.ru/commentsgate/ajax/comments/{thread_id}/rendered?"
        return self._http_get(
            url,
            headers=self._ajax_headers(referer=f"https://www.vl.ru/{company}"),
            params={"theme": "company", "moderatorMode": "1", "before": str(before)},
        )

    def get_avg_history(self, company_id: int | str) -> Response:
        url = f"https://www.vl.ru/ajax/company-history-votes?companyId={company_id}"
        return self._http_get(
            url,
            headers=self._ajax_headers(),
            params={"companyId": company_id},
        )

    def get_company_page(self, company: str) -> Response:
        url = f"https://www.vl.ru/{company}"
        return self._http_get(url)


HttpGet = Callable[..., Response]
