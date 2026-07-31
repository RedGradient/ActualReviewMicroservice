import re
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

from playwright.sync_api import Page

from common_parser.models import BranchPlatform, Review


def _build_url(org_id) -> str:
    return f"https://yandex.com/maps/org/{org_id}/reviews"


def _org_id_from_url(url: str) -> str | None:
    """
    /maps/org/{x}                 -> x
    /maps/org/{x}/(any)           -> x
    /maps/org/{x}/{y}             -> y
    /maps/org/{x}/{y}/(any)       -> y

    /maps/abc/def/
        ?ll=33.086466%2C57.152557
        &mode=poi
        &poi%5Bpoint%5D=33.085168%2C57.154008
        &poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D12345678
        &z=16                     -> 12345678
    """

    if match := re.search(r"/org/(.+)", url):
        org_path = match.group(1).split("?")[0].split("#")[0].strip("/")
        if org_path:
            parts = org_path.split("/")
            if len(parts) == 1:
                return parts[0]
            if len(parts) == 2:
                if parts[1].isdigit():
                    return parts[1]
                return parts[0]
            return parts[1]

    elif poi_uri := parse_qs(urlparse(url).query).get("poi[uri]", [None])[0]:
        poi_uri = unquote(poi_uri)
        if oid_match := re.search(r"oid=(\d+)", poi_uri):
            return oid_match.group(1)

    return None

def _existing_review_keys(branch_platform: BranchPlatform) -> set[tuple[object, str]]:
    return set(Review.objects.filter(branch_platform=branch_platform).values_list("published_date", "content"))


def _review_exists(branch_platform: BranchPlatform, review) -> bool:
    return Review.objects.filter(
        branch_platform=branch_platform, published_date=review["published_date"], content=review["content"]
    ).exists()
