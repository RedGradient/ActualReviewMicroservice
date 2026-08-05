from __future__ import annotations

from datetime import datetime
from typing import Any

from common_parser.models import BranchPlatform


def convert_2gis_reviews_to_model_data(
    branch_platform: BranchPlatform, review_data: dict[str, Any], firm_id: str
) -> dict[str, Any]:
    """Преобразует отзыв 2GIS API в dict для create_review."""
    try:
        published_date = datetime.fromisoformat(review_data["date_created"])
    except (KeyError, ValueError, TypeError):
        published_date = datetime.now()

    avatar_url = review_data.get("user", {}).get("photo_preview_urls", {}).get("url", "")

    photos: list[str] = []
    for photo in review_data.get("photos", []):
        preview_url = photo.get("preview_urls", {}).get("url")
        if preview_url:
            photos.append(preview_url)

    review_id = review_data.get("id")
    review_url = f"https://2gis.ru/reviews/{firm_id}/review/{review_id}" if review_id else None

    return {
        "branch_platform": branch_platform,
        "author": review_data.get("user", {}).get("name", "Аноним"),
        "avatar": avatar_url or None,
        "video": None,
        "photos": ",".join(photos),
        "published_date": published_date,
        "rating": review_data.get("rating", 5),
        "content": review_data.get("text", ""),
        "review_url": review_url,
    }
