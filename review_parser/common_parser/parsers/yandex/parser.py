from datetime import datetime

from loguru import logger
from playwright.sync_api import Locator, sync_playwright

from common_parser.models import BranchPlatform
from common_parser.parsers.helpers import _update_branch_platform
from common_parser.parsers.yandex.helpers import _build_url, _org_id_from_url, _review_exists
from common_parser.tools.create_objects import (
    create_review,
    get_or_create_branch_platform,
    get_or_create_Organization,
)
from common_parser.types import ParseResult, ReviewsBundle

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def create_yandex_reviews(
    url: str, inn: str, org_name: str = "", address: str = "", count: str = 50
) -> tuple[int, int]:
    if (ogr_id := _org_id_from_url(url)) is None:
        raise ValueError(f"Invalid Yandex Maps url: {url!r}")

    organization = get_or_create_Organization(inn, org_name)
    branch_platform = get_or_create_branch_platform(
        organization=organization,
        address=address,
        provider="yandex",
        url=url,
    )

    bundle = fetch_new_reviews(ogr_id, branch_platform)
    _update_branch_platform(branch_platform, bundle)
    branch_platform.save()

    created = 0
    for review in bundle.reviews:
        if create_review(review):
            created += 1

    parsed = len(bundle.reviews)
    logger.info(f"Yandex create finished: url={url} branch_address={address} parsed={parsed} created={created}")
    return parsed, created


def parse_el(review: Locator) -> dict:
    carousel = review.locator(".business-review-view__carousel")
    photos = []
    if carousel.count() > 0:
        photos = carousel.locator("img.business-review-media__item-img").evaluate_all("els => els.map(el => el.src)")
    author = review.locator('[itemprop="name"]').inner_text()
    avatar = review.locator('meta[itemprop="image"]').get_attribute("content")
    rating = review.locator('meta[itemprop="ratingValue"]').get_attribute("content")
    date_iso = review.locator('meta[itemprop="datePublished"]').get_attribute("content")

    published_date: datetime | None = None
    if date_iso:
        published_date = datetime.fromisoformat(date_iso).replace(tzinfo=None)
    text = review.locator(".business-review-view__body .spoiler-view__text-container").inner_text()

    return {
        "author": author,
        "avatar": avatar,
        "rating": rating,
        "published_date": published_date,
        "content": text,
        "photos": photos,
    }


def fetch_new_reviews(
    org_id: str,
    branch_platform: BranchPlatform,
) -> ReviewsBundle:
    # org_id example: 1395883131
    with sync_playwright() as p:
        browser = p.firefox.connect("ws://localhost:3000/", headers=HEADERS)
        page = browser.new_page()
        page.goto(_build_url(org_id))

        rating_text = page.locator(".business-summary-rating-badge-view__rating").inner_text()
        scroll_container = page.locator(".scroll__container")
        processed = 0
        new_reviews = []
        no_new_batches = 0

        while True:
            reviews = page.locator(".business-reviews-card-view__review")
            all_reviews_els = reviews.all()
            new_review_els = all_reviews_els[processed:]

            # Прекращаем скроллить после трех неудачных попыток
            if not new_review_els:
                scroll_container.evaluate("el => el.scrollTop = el.scrollHeight")
                page.wait_for_timeout(1500)
                no_new_batches += 1
                if no_new_batches >= 3:
                    break
                continue

            no_new_batches = 0

            for review_el in new_review_els:
                review = parse_el(review_el)
                if _review_exists(branch_platform, review):
                    return ReviewsBundle(count=len(new_reviews), rating=rating_text, reviews=new_reviews)
                new_reviews.append(review)
                processed += 1

            scroll_container.evaluate("el => el.scrollTop = el.scrollHeight")
            page.wait_for_timeout(1500)

    return ReviewsBundle(count=len(new_reviews), rating=rating_text, reviews=new_reviews)


class YandexMapParser:
    provider = "yandex"

    def run(
        self,
        url: str,
        inn: str,
        *,
        org_name: str = "",
        address: str = "",
        limit: int = 50,
    ) -> ParseResult:
        parsed, created = create_yandex_reviews(
            url=url,
            inn=inn,
            org_name=org_name,
            address=address,
        )
        return ParseResult(parsed, created)
