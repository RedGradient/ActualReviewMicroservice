import json
import os
import re
from datetime import datetime
from typing import Any, Callable

from loguru import logger
from requests import Response

from common_parser.services.http_client import get as http_get
from common_parser.types import ReviewsBundle

from common_parser.tools.create_objects import (
        create_review,
        get_or_create_Branch,
        get_or_create_Organization,
    )
from twogis_parser.tools.to_reviews import convert_2gis_reviews_to_model_data


TWOGIS_API_KEY = os.getenv("TWOGIS_API_KEY", "37c04fe6-a560-4549-b459-02309cf643ad")


def get_reviews(firm_id: str, limit: int, offset: int = 0) -> Response:
    return http_get(_build_api_url(firm_id, limit=limit, offset=offset))




def firm_id_from_url(url: str) -> str | None:
    match = re.search(r"/firm/(\d+)", url)
    return match.group(1) if match else None


def _build_api_url(firm_id: str, *, limit: int = 50, offset: int = 0) -> str:
    return (
        f"https://public-api.reviews.2gis.com/2.0/branches/{firm_id}/reviews"
        f"?limit={limit}&offset={offset}&is_advertiser=true"
        f"&fields=meta.branch_rating,meta.branch_reviews_count,meta.total_count"
        f"&without_my_first_review=false&rated=true&sort_by=date_edited"
        f"&key={TWOGIS_API_KEY}&locale=ru_RU"
    )

def fetch_all_reviews(
    firm_id: str,
    limit: int = 50,
    get_reviews_page: Callable[[str, int, int], Response] = get_reviews
) -> ReviewsBundle:
    first: ReviewsBundle | None = None
    all_reviews: list[dict[str, Any]] = []

    while True:
        response = get_reviews_page(firm_id, limit, offset=len(all_reviews))
        response.raise_for_status()

        bundle = parse(response.text)
        if first is None:
            first = bundle

        all_reviews.extend(bundle.reviews)

        if not bundle.reviews or len(bundle.reviews) < limit:
            break

        if first.count is not None and len(all_reviews) >= first.count:
            break

    if first is None:
        raise TwoGisParseError("2GIS returned no data")

    return ReviewsBundle(
        rating=first.rating,
        count=first.count,
        reviews=all_reviews,
    )


def create_2gis_reviews(
    url: str,
    inn: str,
    org_name: str = "",
    address: str = "",
    count: int = 50,
) -> tuple[int, int]:
    if (firm_id := firm_id_from_url(url)) is None:
        raise ValueError(f"Invalid 2GIS url: {url!r}")

    bundle = fetch_all_reviews(firm_id, limit=count)
    fetched_count = len(bundle.reviews)

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="twogis_map_url",
        url=url,
        review_count_name="twogis_review_count",
        review_count=str(bundle.count if bundle.count is not None else fetched_count),
        review_avg_name="twogis_review_avg",
        review_avg=str(bundle.rating) if bundle.rating is not None else "",
    )

    branch.twogis_parse_date = datetime.now()
    branch.save()

    cnt = 0
    for review in bundle.reviews:
        if create_review(
            convert_2gis_reviews_to_model_data(branch=branch, review_data=review, url=url)
        ):
            cnt += 1

    logger.info(
        "2GIS create finished: url={} branch_address={} parsed={} created={}",
        url,
        address,
        fetched_count,
        cnt,
    )

    return fetched_count, cnt


class TwoGisParseError(Exception):
    pass


def parse(response_text: str) -> ReviewsBundle:
    try:
        response_dict = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from 2GIS: {}", exc.msg)
        raise TwoGisParseError("2GIS returned invalid JSON") from exc

    try:
        return ReviewsBundle(
            rating=response_dict["meta"]["branch_rating"],
            count=response_dict["meta"]["branch_reviews_count"],
            reviews=response_dict["reviews"],
        )
    except KeyError as exc:
        logger.error("Unexpected 2GIS response structure, missing key: {}", exc)
        raise TwoGisParseError("2GIS response has unexpected structure") from exc
