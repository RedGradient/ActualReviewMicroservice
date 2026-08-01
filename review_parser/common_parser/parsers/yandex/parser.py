from datetime import datetime

from celery.result import AsyncResult
from loguru import logger
from playwright.sync_api import Locator, sync_playwright

from common_parser.models import BranchPlatform
from common_parser.parsers.helpers import _update_branch_platform
from common_parser.parsers.yandex.helpers import (
    _build_url,
    _existing_review_keys,
    _org_id_from_url,
    _parse_global_rating,
)
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

    logger.info("Yandex parser started for url: {}", url)

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
        else:
            logger.warning("Yandex parser, serialization error in {}", review)

    parsed = len(bundle.reviews)
    logger.info(f"Yandex create finished: url={url} branch_address={address} parsed={parsed} created={created}")
    return parsed, created


def parse_el(review: Locator) -> dict | None:
    try:
        data = review.evaluate(
            """
            el => {
                const photos = [...el.querySelectorAll(
                    ".business-review-view__carousel img.business-review-media__item-img"
                )].map(img => img.src);
                return {
                    author: el.querySelector('[itemprop="name"]')?.textContent?.trim() ?? "",
                    avatar: el.querySelector('meta[itemprop="image"]')?.getAttribute("content") ?? "",
                    rating: el.querySelector('meta[itemprop="ratingValue"]')?.getAttribute("content") ?? "",
                    date_iso: el.querySelector('meta[itemprop="datePublished"]')?.getAttribute("content") ?? "",
                    text: el.querySelector(
                        ".business-review-view__body .spoiler-view__text-container"
                    )?.textContent?.trim() ?? "",
                    photos,
                };
            }
            """,
            timeout=5000,
        )
    except Exception as exc:
        logger.warning(f"Failed to parse review element, skipping: {exc}")
        return None

    published_date: datetime | None = None
    if data["date_iso"]:
        published_date = datetime.fromisoformat(data["date_iso"]).replace(tzinfo=None)

    return {
        "author": data["author"],
        "avatar": data["avatar"] or None,
        "rating": data["rating"] or None,
        "published_date": published_date,
        "content": data["text"],
        "photos": ", ".join(data["photos"]),
    }


def fetch_new_reviews(
    org_id: str,
    branch_platform: BranchPlatform,
) -> ReviewsBundle:
    existing_keys = _existing_review_keys(branch_platform)

    with sync_playwright() as p:
        browser = p.firefox.connect("ws://localhost:3000/", headers=HEADERS)
        page = browser.new_page()
        page.goto(_build_url(org_id))

        rating = _parse_global_rating(page)
        scroll_container = page.locator(".scroll__container")

        # Установить сортировку "сначала новые"
        page.locator(".rating-ranking-view").click()
        new_first_button = page.locator('.rating-ranking-view__popup-line[aria-label="New first"]')
        new_first_button.wait_for()
        new_first_button.click()
        page.wait_for_timeout(2000)

        processed = 0
        new_reviews = []
        no_new_batches = 0
        no_new_batches_limit = 3
        pg = 1

        while True:
            reviews = page.locator(".business-reviews-card-view__review")
            all_reviews_els = reviews.all()
            new_review_els = all_reviews_els[processed:]

            # Прекращаем скроллить после трех неудачных попыток
            if not new_review_els:
                scroll_container.evaluate("el => el.scrollTop = el.scrollHeight")
                page.wait_for_timeout(1500)
                no_new_batches += 1
                logger.info(
                    "Yandex parser, повторная попытка получить новые отзывы {}/{}", no_new_batches, no_new_batches_limit
                )
                if no_new_batches >= 3:
                    break
                continue

            no_new_batches = 0

            for review_el in new_review_els:
                review = parse_el(review_el)
                if review is None:
                    processed += 1
                    continue
                review_key = (review["published_date"], review["content"])
                if review_key in existing_keys:
                    logger.info("Yandex parser, Знакомый отзыв, совпадение по {}. Парсинг остановлен", review_key)
                    return ReviewsBundle(count=len(new_reviews), rating=rating, reviews=new_reviews)

                review["branch_platform"] = branch_platform
                new_reviews.append(review)
                processed += 1

            scroll_container.evaluate("el => el.scrollTop = el.scrollHeight")
            page.wait_for_timeout(1500)

            logger.info("Yandex parsing...page {}, parsed {}", pg, len(new_reviews))
            pg += 1

    return ReviewsBundle(count=len(new_reviews), rating=rating, reviews=new_reviews)


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

    def run_delay(
        self,
        url: str,
        inn: str,
        *,
        org_name: str = "",
        address: str = "",
    ) -> str:
        organization = get_or_create_Organization(inn, org_name)
        branch_platform = get_or_create_branch_platform(
            organization=organization,
            address=address,
            provider="yandex",
            url=url,
        )

        from common_parser.tasks import parse_yandex_async

        task: AsyncResult = parse_yandex_async.delay(branch_platform.pk)
        return task.id
