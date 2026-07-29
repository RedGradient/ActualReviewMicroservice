from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

import bs4
from bs4 import BeautifulSoup
from loguru import logger
from requests import Response

from common_parser.models import BranchPlatform, Review
from common_parser.parsers.helpers import _update_branch_platform
from common_parser.services.http_client import get as http_get
from common_parser.tools.create_objects import (
    create_review,
    get_or_create_branch_platform,
    get_or_create_Organization,
)
from common_parser.types import ParseResult, ReviewsBundle

HttpGet = Callable[..., Response]


def get_company_rating(html: str) -> float | None:
    soup = BeautifulSoup(html, "html.parser")
    rating_el = soup.find("ul", class_="stars control")
    if not isinstance(rating_el, bs4.Tag):
        return None
    rating = rating_el.get("data-default")
    if not isinstance(rating, str):
        return None
    try:
        return float(rating.replace(",", "."))
    except ValueError:
        logger.warning("VL company rating: invalid data-default={!r}", rating)
        return None


def get_company_review_count(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    rev_count_el = soup.find("a", class_="hash-link", href="#comments")
    if not isinstance(rev_count_el, bs4.Tag):
        return None
    text = rev_count_el.get_text(" ", strip=True)
    match = re.search(r"(\d+)", text)
    if not match:
        logger.warning("VL company review count: no digits in {!r}", text)
        return None
    try:
        return int(match.group(1))
    except ValueError:
        logger.warning("VL company review count: invalid value {!r}", match.group(1))
        return None


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

            if not (comment_id := review_item.get("comment")):
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
                    "comment_id": comment_id,
                    "author": author,
                    "avatar": avatar,
                    "video": None,
                    "photos": photos,
                    "published_date": published_date,
                    "rating": rating,
                    "content": content,
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

    while data["data"]["lastCommentId"] and data["data"]["commentsCount"] and response.status_code == 200:
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


def _review_exists(branch_platform: BranchPlatform, review: dict[str, Any]) -> bool:
    return Review.objects.filter(
        branch_platform=branch_platform,
        external_id=review["comment_id"],
    ).exists()


def fetch_new_reviews(
    company: str,
    branch_platform: BranchPlatform,
    *,
    client: VLClient | None = None,
) -> ReviewsBundle:
    client = client or VLClient()
    all_reviews: list[dict[str, Any]] = []

    response = client.get_company_page(company)
    response.raise_for_status()

    company_review_count = get_company_review_count(html=response.text)
    company_rating = get_company_rating(html=response.text)

    response = client.get_thread(company)
    response.raise_for_status()

    data = response.json()
    thread_id = data["data"]["threadId"]

    while True:
        for review in parse_vlru_reviews(data["data"]["content"]):
            if _review_exists(branch_platform, review):
                count = len(all_reviews)
                logger.info("VL new reviews: company={} count={}", company, count)
                return ReviewsBundle(rating=company_rating, count=company_review_count, reviews=all_reviews)
            all_reviews.append(review)

        if not (data["data"]["lastCommentId"] and data["data"]["commentsCount"] and response.status_code == 200):
            break

        response = client.get_comments_page(
            company,
            thread_id,
            data["data"]["lastCommentId"],
        )
        response.raise_for_status()
        data = response.json()

    count = len(all_reviews)
    logger.info("VL new reviews: company={} count={}", company, count)
    return ReviewsBundle(rating=company_rating, count=company_review_count, reviews=all_reviews)


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

    organization = get_or_create_Organization(inn, org_name)
    branch_platform = get_or_create_branch_platform(
        organization=organization,
        address=address,
        provider="vlru",
        url=url,
    )

    bundle = fetch_new_reviews(company, branch_platform, client=client)
    _update_branch_platform(branch_platform, bundle)
    branch_platform.save()

    created_count = 0
    for review in bundle.reviews:
        review["branch_platform"] = branch_platform
        if create_review(review):
            created_count += 1

    fetched_count = len(bundle.reviews)
    logger.info(
        "VL create finished: url={} branch_address={} parsed={} created={}",
        url,
        address,
        fetched_count,
        created_count,
    )
    return fetched_count, created_count


class VlruParser:
    provider = "vlru"

    def __init__(self, *, client: VLClient | None = None) -> None:
        self._client = client

    def run(
        self,
        url: str,
        inn: str,
        *,
        org_name: str = "",
        address: str = "",
        limit: int = 50,
    ) -> ParseResult:
        parsed, created = create_vlru_reviews(
            url=url,
            inn=inn,
            org_name=org_name,
            address=address,
            count=limit,
            client=self._client,
        )
        return ParseResult(parsed, created)
