from __future__ import annotations

from datetime import datetime

from loguru import logger

from common_parser.models import BranchPlatform, Review, Video
from common_parser.types import ReviewsBundle
from review_parser.settings import MAX_REVIEWS, MAX_VIDEO_COUNT


def _update_branch_platform(branch_platform: BranchPlatform, bundle: ReviewsBundle) -> BranchPlatform:
    fetched_count = len(bundle.reviews)

    branch_platform.review_count = bundle.count if bundle.count is not None else fetched_count
    if bundle.rating is not None:
        branch_platform.review_avg = str(bundle.rating)
    branch_platform.parsed_at = datetime.now()

    return branch_platform


def _delete_overflow_reviews(branch_platform_id: int):
    """Удаляет старые отзывы по overflow"""

    old_count = Review.objects.filter(branch_platform_id=branch_platform_id).count()
    overflow = old_count - MAX_REVIEWS
    if overflow > 0:
        ids_to_delete = (
            Review.objects.filter(branch_platform_id=branch_platform_id)
            .order_by("published_date")
            .values_list("pk", flat=True)[:overflow]
        )
        Review.objects.filter(pk__in=ids_to_delete).delete()
        remaining = Review.objects.filter(branch_platform_id=branch_platform_id).count()
        logger.info(
            "overflow deleted={} branch_platform_id={} remaining={}",
            overflow,
            branch_platform_id,
            remaining,
        )


def _delete_overflow_videos(playlist_db_id: int):
    """Удаляет старые видео по overflow"""

    old_count = Video.objects.filter(playlist_id=playlist_db_id).count()
    overflow = old_count - MAX_VIDEO_COUNT
    if overflow > 0:
        ids_to_delete = (
            Video.objects.filter(playlist_id=playlist_db_id)
            .order_by("published_date")
            .values_list("pk", flat=True)[:overflow]
        )
        Video.objects.filter(pk__in=ids_to_delete).delete()
        remaining = Video.objects.filter(playlist_id=playlist_db_id).count()
        logger.info(
            "overflow deleted={} playlist_id={} remaining={}",
            overflow,
            playlist_db_id,
            remaining,
        )
