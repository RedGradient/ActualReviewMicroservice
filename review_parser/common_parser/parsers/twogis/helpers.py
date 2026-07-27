from __future__ import annotations

import os
import re
from datetime import datetime

from requests import Response

from common_parser.models import BranchPlatform, Review
from common_parser.services.http_client import get as http_get
from common_parser.types import ReviewsBundle

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
        f"&without_my_first_review=false&rated=true&sort_by=date_created"
        f"&key={TWOGIS_API_KEY}&locale=ru_RU"
    )


def _review_exists(branch_platform: BranchPlatform, review) -> bool:
    return Review.objects.filter(
        branch_platform=branch_platform,
        author=review["user"]["name"],
        content=review["text"]
    ).exists()


def _update_branch_platform(branch_platform: BranchPlatform, bundle: ReviewsBundle) -> BranchPlatform:
    fetched_count = len(bundle.reviews)

    branch_platform.review_count = bundle.count if bundle.count is not None else fetched_count
    if bundle.rating is not None:
        branch_platform.review_avg = str(bundle.rating)
    branch_platform.parsed_at = datetime.now()

    return branch_platform
