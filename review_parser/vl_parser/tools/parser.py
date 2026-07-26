from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable

from bs4 import BeautifulSoup
from loguru import logger
from requests import Response

from common_parser.services.http_client import get as http_get
from common_parser.tools.create_objects import (
    create_review,
    get_or_create_Branch,
    get_or_create_Organization,
)
from common_parser.types import ReviewsBundle

HttpGet = Callable[..., Response]


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


def get_company_from_url(url: str) -> str | None:
    match = re.search(r"/([^/]+)$", url)
    return match.group(1) if match else None


def parse_vlru_reviews(html_content: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_content, "html.parser")

    reviews_list = soup.find("ul", {"id": "CommentsList"}) or soup
    reviews: list[dict[str, Any]] = []

    for review_item in reviews_list.find_all("li", recursive=False):
        try:
            if review_item.get("data-parent-id"):
                continue

            if not review_item.get("comment"):
                continue

            timestamp = int(review_item.get("data-timestamp"))
            published_date = datetime.fromtimestamp(timestamp)

            author_block = review_item.find("span", class_="user-name")
            author = author_block.get_text(strip=True) if author_block else "Anonymous"

            avatar_img = review_item.find("img", class_="avatar")
            avatar = avatar_img["src"] if avatar_img else None

            rating = 0
            rating_wrapper = review_item.find("div", class_="cmt-rating-wrapper")
            if rating_wrapper:
                active_rating = rating_wrapper.find("div", class_="active")
                if active_rating and "data-value" in active_rating.attrs:
                    rating = float(active_rating["data-value"]) * 5

            photos = ""
            images_wrapper = review_item.find("div", class_="comment-images-wrapper")
            if images_wrapper:
                items = images_wrapper.find_all("div", class_="item")
                photos = ",".join(item.find("a")["href"] for item in items)

            comment_text = review_item.find("p", class_="comment-text")
            content = comment_text.get_text(strip=True) if comment_text else ""

            reviews.append(
                {
                    "author": author,
                    "avatar": avatar,
                    "video": None,
                    "photos": photos,
                    "published_date": published_date,
                    "rating": rating,
                    "content": content,
                    "provider": "vlru",
                }
            )
        except Exception as exc:
            logger.warning("VL parse review failed: {}", exc)
            continue

    return reviews


def fetch_all_reviews(company: str, *, client: VLClient | None = None) -> ReviewsBundle:
    client = client or VLClient()

    response = client.get_thread(company)
    response.raise_for_status()

    data = response.json()
    reviews = parse_vlru_reviews(data["data"]["content"])
    thread_id = data["data"]["threadId"]

    while (
        data["data"]["lastCommentId"]
        and data["data"]["commentsCount"]
        and response.status_code == 200
    ):
        response = client.get_comments_page(
            company,
            thread_id,
            data["data"]["lastCommentId"],
        )
        response.raise_for_status()
        data = response.json()
        reviews.extend(parse_vlru_reviews(data["data"]["content"]))

    count = len(reviews)
    logger.info("VL parsed reviews: company={} count={}", company, count)

    return ReviewsBundle(
        rating=5,
        count=count,
        reviews=reviews,
    )


def _apply_avg_rating_from_history(branch, response: Response) -> None:
    response.raise_for_status()
    response_dict = json.loads(response.text)

    for item in response_dict["history"].values():
        avg = float(item)
        if avg < 4:
            avg = 4
        branch.vlru_review_avg = avg
        break


def create_vlru_reviews(
    url: str,
    inn: str,
    org_name: str = "",
    address: str = "",
    count: str | int = 50,
    *,
    client: VLClient | None = None,
) -> tuple[int, int]:
    if (company := get_company_from_url(url)) is None:
        raise ValueError(f"Invalid VL.ru url: {url!r}")

    client = client or VLClient()
    bundle = fetch_all_reviews(company, client=client)

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="vlru_url",
        url=url,
        review_count_name="vlru_review_count",
        review_count=bundle.count,
        review_avg_name="vlru_review_avg",
        review_avg=-1,
    )

    if branch.vlru_org_id:
        _apply_avg_rating_from_history(branch, client.get_avg_history(branch.vlru_org_id))

    branch.vlru_parse_date = datetime.now()
    branch.save()

    for review in bundle.reviews:
        review["branch"] = branch

    created_count = 0
    for review in bundle.reviews:
        if create_review(review):
            created_count += 1

    logger.info(
        "VL create finished: url={} branch_address={} parsed={} created={}",
        url,
        address,
        len(bundle.reviews),
        created_count,
    )
    return len(bundle.reviews), created_count
