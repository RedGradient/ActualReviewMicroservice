from __future__ import annotations

import re
from typing import Any

import bs4
from bs4 import BeautifulSoup
from loguru import logger

from common_parser.models import BranchPlatform, Review
from common_parser.tools.hash import normalize_and_hash


def get_company_from_url(url: str) -> str | None:
    url = url.split("#", 1)[0].rstrip("/")
    match = re.search(r"/([^/]+)$", url)
    return match.group(1) if match else None


def _review_exists(branch_platform: BranchPlatform, review: dict[str, Any]) -> bool:
    return Review.objects.filter(
        branch_platform=branch_platform,
        author=review["author"],
        content_hash=normalize_and_hash(review["content"]),
        published_date=review["published_date"],
    ).exists()


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
