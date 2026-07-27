from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from loguru import logger
from requests import Response

from common_parser.models import BranchPlatform, Review
from common_parser.parsers.twogis.helpers import get_reviews, firm_id_from_url, _review_exists
from common_parser.parsers.helpers import _update_branch_platform
from common_parser.types import ReviewsBundle, ParseResult

from common_parser.tools.create_objects import (
    create_review,
    get_or_create_Organization, get_or_create_branch_platform,
)
from common_parser.parsers.twogis.to_reviews import convert_2gis_reviews_to_model_data


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


def fetch_new_reviews(
        firm_id: str,
        branch_platform: BranchPlatform,
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

        for review in bundle.reviews:
            if _review_exists(branch_platform, review):
                return ReviewsBundle(
                    rating=first.rating,
                    count=first.count,
                    reviews=all_reviews,
                )
            all_reviews.append(review)

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

    organization = get_or_create_Organization(inn, org_name)
    branch_platform = get_or_create_branch_platform(
        organization=organization,
        address=address,
        provider="2gis",
        url=url,
    )

    bundle = fetch_new_reviews(firm_id, branch_platform, limit=count)
    _update_branch_platform(branch_platform, bundle)
    branch_platform.save()

    cnt = 0
    for review in bundle.reviews:
        if create_review(
                convert_2gis_reviews_to_model_data(
                    branch_platform=branch_platform,
                    review_data=review,
                    url=url,
                )
        ):
            cnt += 1

    fetched_count = len(bundle.reviews)
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


class TwoGisParser:
    provider = "2gis"

    def run(
            self,
            url: str,
            inn: str,
            *,
            org_name: str = "",
            address: str = "",
            limit: int = 50,
    ) -> ParseResult:
        parsed, created = create_2gis_reviews(
            url=url,
            inn=inn,
            org_name=org_name,
            address=address,
            count=limit,
        )
        return ParseResult(parsed, created)
