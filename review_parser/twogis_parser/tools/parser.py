import json
import time
import re
from common_parser.tools.create_objects import get_or_create_Branch, get_or_create_Organization, create_review
from twogis_parser.tools.to_reviews import convert_2gis_reviews_to_model_data
from loguru import logger
from common_parser.models import Branch
from datetime import datetime
from common_parser.services.http_client import get as http_get

@logger.catch
def create_2gis_reviews(url: str, inn: str, org_name: str ="", address: str ="", count: str = 50) -> int:
    dict_2gis = parse(get_api_url_from_2gis(url, count or 50))

    new_dict = [1]
    try:
        while len(new_dict):
            new_dict = parse(get_api_url_from_2gis_offset(url, count or 50, len(dict_2gis['reviews'])))["reviews"]
            dict_2gis['reviews'] += new_dict
    except Exception:
        logger.exception("2GIS pagination failed")

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="twogis_map_url",
        url=url,
        review_count_name = 'twogis_review_count',
        review_count = dict_2gis['count'],
        review_avg_name = 'twogis_review_avg',
        review_avg = dict_2gis['rating']
    )

    branch.twogis_parse_date = datetime.now()
    branch.save()

    cnt = 0

    for review in dict_2gis['reviews']:
        if create_review(convert_2gis_reviews_to_model_data(branch=branch, review_data=review, url=url)):
            cnt += 1

    logger.info(
        f"2GIS create finished: url={url} branch_address={address} parsed={len(dict_2gis.get('reviews', []))} created={cnt}"
    )
    return (len(dict_2gis['reviews']), cnt)

def get_api_url_from_2gis(url: str, limit: int = 50) -> str:

    pattern = r'/firm/(\d+)'
    match = re.search(pattern, url)
    if match:
        firm_id = match.group(1)
    else:
        return None
    return f"https://public-api.reviews.2gis.com/2.0/branches/{firm_id}/reviews?limit={limit}&is_advertiser=true&fields=meta.branch_rating,meta.branch_reviews_count,meta.total_count&without_my_first_review=false&rated=true&sort_by=date_edited&key=37c04fe6-a560-4549-b459-02309cf643ad&locale=ru_RU" 

def get_api_url_from_2gis_offset(url: str, limit: int = 50, offset: int = 50) -> str:

    pattern = r'/firm/(\d+)'
    match = re.search(pattern, url)
    if match:
        firm_id = match.group(1)
    else:
        return None
    return f"https://public-api.reviews.2gis.com/2.0/branches/{firm_id}/reviews?limit={limit}&offset={offset}&is_advertiser=true&fields=meta.branch_rating,meta.branch_reviews_count,meta.total_count&without_my_first_review=false&rated=true&sort_by=date_edited&key=37c04fe6-a560-4549-b459-02309cf643ad&locale=ru_RU" 

@logger.catch
def parse(url):
    response = http_get(url)

    if response.status_code != 200:
        time.sleep(30)

        response = http_get(url)

    response_text = response.text
    response_dict = json.loads(response_text)

    if response_dict["meta"]["total_count"] == 0:
        time.sleep(30)
        response = http_get(url)
        response_text = response.text
        response_dict = json.loads(response_text)

    if response_dict["meta"]["total_count"] == 0:
        logger.error("2GIS parse failed: total_count=0")
        return {'error': 'parse failed'}

    return {
        'rating': response_dict["meta"]["branch_rating"],
        'count': response_dict["meta"]["branch_reviews_count"],
        'reviews': response_dict["reviews"]
    }

