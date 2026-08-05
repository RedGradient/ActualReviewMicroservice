from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from loguru import logger
from requests import Response

from common_parser.models import BranchPlatform
from common_parser.parsers.helpers import _delete_overflow_reviews, _update_branch_platform
from common_parser.parsers.twogis.helpers import _review_exists, firm_id_from_url, get_reviews
from common_parser.parsers.twogis.to_reviews import convert_2gis_reviews_to_model_data
from common_parser.tools.create_objects import (
    create_review,
    get_or_create_branch_platform,
    get_or_create_Organization,
)
from common_parser.types import ParseResult, ReviewsBundle
from review_parser.settings import MAX_REVIEWS


def fetch_new_reviews(
    firm_id: str,
    branch_platform: BranchPlatform,
    limit: int = 50,
    get_reviews_page: Callable[[str, int, int], Response] = get_reviews,
) -> ReviewsBundle:
    logger.debug("fetch started firm_id={} limit={}", firm_id, limit)
    first: ReviewsBundle | None = None
    all_reviews: list[dict[str, Any]] = []

    while True:
        offset = len(all_reviews)
        response = get_reviews_page(firm_id, limit, offset=offset)
        response.raise_for_status()

        bundle = parse(response.text)
        if first is None:
            first = bundle

        batch_size = len(bundle.reviews)
        logger.debug("fetch page offset={} batch={} total={}", offset, batch_size, offset + batch_size)

        for review in bundle.reviews:
            if _review_exists(branch_platform, review):
                new_count = len(all_reviews)
                logger.info(
                    "fetch stopped reason=existing_review external_id={} new={}",
                    review.get("id"),
                    new_count,
                )
                return ReviewsBundle(
                    rating=first.rating,
                    count=first.count,
                    reviews=all_reviews,
                )
            if len(all_reviews) >= MAX_REVIEWS:
                logger.info(
                    "fetch stopped reason=max_reviews limit={} new={}",
                    MAX_REVIEWS,
                    len(all_reviews),
                )
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
        logger.error("fetch failed reason=empty_response firm_id={}", firm_id)
        raise TwoGisParseError("2GIS returned no data")

    logger.info(
        "fetch done new={} rating={} site_count={}",
        len(all_reviews),
        first.rating,
        first.count,
    )
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
    started_at = time.monotonic()
    if (firm_id := firm_id_from_url(url)) is None:
        raise ValueError(f"Invalid 2GIS url: {url!r}")

    logger.info("started url={} firm_id={} org_inn={}", url, firm_id, inn)

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

    created = 0
    skipped = 0
    for review in bundle.reviews:
        if create_review(
            convert_2gis_reviews_to_model_data(branch_platform=branch_platform, review_data=review, firm_id=firm_id)
        ):
            created += 1
        else:
            skipped += 1

    _delete_overflow_reviews(branch_platform.id)

    parsed = len(bundle.reviews)
    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "finished parsed={} created={} skipped={} duration_ms={}",
        parsed,
        created,
        skipped,
        duration_ms,
    )

    return parsed, created


class TwoGisParseError(Exception):
    pass


def parse(response_text: str) -> ReviewsBundle:
    try:
        response_dict = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.error("parse failed reason=invalid_json detail={}", exc.msg)
        raise TwoGisParseError("2GIS returned invalid JSON") from exc

    try:
        return ReviewsBundle(
            rating=response_dict["meta"]["branch_rating"],
            count=response_dict["meta"]["branch_reviews_count"],
            reviews=response_dict["reviews"],
        )
    except KeyError as exc:
        logger.error("parse failed reason=missing_key key={}", exc)
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
        with logger.contextualize(provider=self.provider):
            parsed, created = create_2gis_reviews(
                url=url,
                inn=inn,
                org_name=org_name,
                address=address,
                count=limit,
            )
            return ParseResult(parsed, created)
