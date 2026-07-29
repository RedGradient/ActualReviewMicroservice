import re
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from common_parser.services.http_client import get as http_get
from common_parser.tools.create_objects import (
    create_review,
    get_or_create_Branch,
    get_or_create_Organization,
)
from common_parser.tools.parse_date_string import parse_date_string

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


@logger.catch
def parse(url: str, limit: int | None = None) -> dict:
    logger.info(f"Yandex parse started: url={url} limit={limit}")
    response = http_get(url, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    reviews_counter = -1
    rating_global = -1.0

    reviews_tab = soup.select_one(".tabs-select-view__title._name_reviews")
    if reviews_tab:
        counter_el = reviews_tab.select_one(".tabs-select-view__counter")
        if counter_el and counter_el.text:
            reviews_counter = counter_el.text.strip()

    stars_block = soup.select_one(".business-summary-rating-badge-view")
    if stars_block:
        rating_parts = [
            el.get_text(strip=True) for el in stars_block.select(".business-summary-rating-badge-view__rating-text")
        ]
        if rating_parts:
            rating_text = "".join(rating_parts)
            rating_text = rating_text.replace("\xa0", "").replace(",", ".").strip()
            try:
                rating_global = float(rating_text)
            except ValueError:
                rating_global = -1.0

    result: list[dict] = []
    count = 0

    review_blocks = soup.select(".business-review-view__info")

    for review_block in review_blocks:
        avatar_img_url = ""
        avatar_el = review_block.select_one(".user-icon-view__icon")
        if avatar_el:
            style_attr = avatar_el.get("style", "")
            match = re.search(r'url\(["\']?(.*?)["\']?\)', style_attr)
            if match:
                avatar_img_url = match.group(1).strip('"')

        author_name_el = review_block.select_one(".business-review-view__author-name")
        author_name = author_name_el.text.strip() if author_name_el else ""

        date_published_el = review_block.select_one(".business-review-view__date")
        date_published_raw = date_published_el.text.strip() if date_published_el else ""

        photos_obj = review_block.select(".business-review-media__item-img")
        image_srcs = []
        for photo in photos_obj:
            src = photo.get("src")
            if src:
                image_srcs.append(src)
        photos = ", ".join(image_srcs)

        stars_count = len(review_block.select(".business-rating-badge-view__star._full"))

        review_text_el = review_block.select_one(".business-review-view__body")
        review_text = review_text_el.text.strip() if review_text_el else ""
        if "Ещё" in review_text:
            review_text = review_text.replace("Ещё", "").strip()

        try:
            result.append(
                {
                    "author": author_name,
                    "avatar": avatar_img_url,
                    "published_date": parse_date_string(date_published_raw),
                    "rating": stars_count,
                    "content": review_text,
                    "provider": "yandex",
                    "photos": photos,
                }
            )
            count += 1
        except Exception:
            print("Ошибка при добавлении ", Exception)

        if limit and limit == count:
            break

    return {
        "count": reviews_counter,
        "rating": rating_global,
        "reviews": result,
    }


def create_yandex_reviews(url: str, inn: str, org_name: str = "", address: str = "", count: str = 50) -> int:
    dict_yandex = parse(url)

    if dict_yandex is None:
        dict_yandex = {"count": 0, "rating": -1, "reviews": []}

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="yandex_map_url",
        url=url,
        review_count_name="yandex_review_count",
        review_count=dict_yandex["count"],
        review_avg_name="yandex_review_avg",
        review_avg=dict_yandex["rating"],
    )

    branch.yandex_parse_date = datetime.now()
    branch.save()

    for d in dict_yandex["reviews"]:
        d["branch"] = branch

    cnt = 0

    for review in dict_yandex["reviews"]:
        if create_review(review):
            cnt += 1

    logger.info(
        f"Yandex create finished: url={url} branch_address={address} parsed={len(dict_yandex['reviews'])} created={cnt}"
    )
    return (len(dict_yandex["reviews"]), cnt)
