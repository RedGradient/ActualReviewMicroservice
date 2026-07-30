import re

from common_parser.models import BranchPlatform, Review


def _build_url(org_id) -> str:
    return f"https://yandex.com/maps/org/{org_id}/reviews"


def _org_id_from_url(url: str) -> str | None:
    match = re.search(r"/org/(\d+)", url)
    return match.group(1) if match else None


def _review_exists(branch_platform: BranchPlatform, review) -> bool:
    return Review.objects.filter(
        branch_platform=branch_platform, published_date=review["published_date"], content=review["content"]
    ).exists()
