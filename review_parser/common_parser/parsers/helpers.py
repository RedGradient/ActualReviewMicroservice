from __future__ import annotations

from datetime import datetime

from common_parser.models import BranchPlatform
from common_parser.types import ReviewsBundle


def _update_branch_platform(branch_platform: BranchPlatform, bundle: ReviewsBundle) -> BranchPlatform:
    fetched_count = len(bundle.reviews)

    branch_platform.review_count = bundle.count if bundle.count is not None else fetched_count
    if bundle.rating is not None:
        branch_platform.review_avg = str(bundle.rating)
    branch_platform.parsed_at = datetime.now()

    return branch_platform
