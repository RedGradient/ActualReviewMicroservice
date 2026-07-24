from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
from common_parser.tools.create_objects import get_or_create_Branch, get_or_create_Organization, create_review
from common_parser.models import Branch
from loguru import logger
from common_parser.services.http_client import get as http_get

def create_vlru_reviews(url: str, inn: str, org_name: str ="", address: str ="", count: str = 50) -> int:

    company = get_company_from_url(url)

    dict_vlru = parse(company)

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="vlru_url",
        url=url,
        review_count_name = 'vlru_review_count',
        review_count = dict_vlru['count'],
        review_avg_name = 'vlru_review_avg',
        review_avg = -1
    )

    if branch.vlru_org_id:      
        response = send_request_vl_avg_review(branch.vlru_org_id)
        response_text = response.text
        response_dict = json.loads(response_text)

        for key, item in response_dict["history"].items():
            avg = float(item)
            if avg < 4:
                avg = 4
            branch.vlru_review_avg = avg 
            break
    
    branch.vlru_parse_date = datetime.now()
    branch.save()

    for d in dict_vlru['reviews']:
        d['branch'] = branch   

    cnt = 0

    for review in dict_vlru['reviews']:
        if create_review(review):
            cnt += 1

    logger.info(
        f"VL create finished: url={url} branch_address={address} parsed={len(dict_vlru.get('reviews', []))} created={cnt}"
    )
    return (len(dict_vlru['reviews']), cnt)

@logger.catch
def parse_vlru_reviews(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    reviews_list = soup.find('ul', {'id': 'CommentsList'})
    
    if not reviews_list:
        reviews_list = soup

    reviews = []
    
    for review_item in reviews_list.find_all('li', recursive=False):
        try:
            if review_item.get('data-parent-id'):
                continue

            if not review_item.get('comment'):
                continue

            comment_id = review_item.get('comment')
            #print(comment_id)
            profile_id = review_item.get('data-profile-id')
            review_type = review_item.get('data-type')
            timestamp = int(review_item.get('data-timestamp'))
            published_date = datetime.fromtimestamp(timestamp)
            
            author_block = review_item.find('span', class_='user-name')
            author = author_block.get_text(strip=True) if author_block else "Anonymous"
            
            # Extract avatar
            avatar_img = review_item.find('img', class_='avatar')
            avatar = avatar_img['src'] if avatar_img else None
            
            # Extract rating
            rating = 0
            rating_wrapper = review_item.find('div', class_='cmt-rating-wrapper')
            if rating_wrapper:
                active_rating = rating_wrapper.find('div', class_='active')
                if active_rating and 'data-value' in active_rating.attrs:
                    rating = float(active_rating['data-value'])
                    rating *= 5
            
            #Extract photos
            photos = ""
            images_wrapper = review_item.find('div', class_='comment-images-wrapper')
            if images_wrapper:
                items = images_wrapper.find_all('div', class_='item')
                photos = ",".join([item.find('a')['href'] for item in items])


            # Extract content
            comment_text = review_item.find('p', class_='comment-text')
            content = comment_text.get_text(strip=True) if comment_text else ""
            
            # Extract likes count
            likes_block = review_item.find('span', class_='likes')
            likes_count = int(likes_block.get('data-like-count', 0)) if likes_block else 0
            
            # Create review dictionary
            review = {
                'author': author,
                'avatar': avatar,
                'video': None, 
                'photos': photos,  
                'published_date': published_date,
                'rating': rating,
                'content': content,
                'provider': 'vlru',
            }
            
            reviews.append(review)
            
        except Exception as e:
            logger.warning(f"VL parse review failed: {e}")
            continue
    
    return reviews

def get_company_from_url(url: str) -> str:
    match = re.search(r'/([^/]+)$', url)
    if match:
        return match.group(1)
    return None

def send_request_vl(company):
    url = f'https://www.vl.ru/commentsgate/ajax/thread/company/{company}/embedded'
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'https://www.vl.ru/{company}'
    }
    params = {'theme': 'company', 'moderatorMode': '1'}

    response = http_get(url, headers=headers, params=params)

    return response

def send_request_vl_comment(company, threadId, before):
    url = f'https://www.vl.ru/commentsgate/ajax/comments/{threadId}/rendered?'
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'https://www.vl.ru/{company}'
    }
    params = {'theme': 'company', 'moderatorMode': '1', 'before': f'{before}'}

    response = http_get(url, headers=headers, params=params)

    return response

def send_request_vl_avg_review(company_id):
    url = f'https://www.vl.ru/ajax/company-history-votes?companyId={company_id}'
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
    }
    params = {'companyId': company_id}

    response = http_get(url, headers=headers, params=params)

    return response

@logger.catch
def parse(company):

    response = send_request_vl(company)
    if response.status_code == 200:
        data = response.json()

        reviews = parse_vlru_reviews(data["data"]["content"])
        threadId = data["data"]["threadId"]

        while data["data"]["lastCommentId"] and data["data"]["commentsCount"] and response.status_code == 200:
            response = send_request_vl_comment(company, threadId, data["data"]["lastCommentId"])
            data = response.json()
            reviews = reviews + parse_vlru_reviews(data["data"]["content"])
            

        count = len(reviews)
        logger.info(f"VL parsed reviews: company={company} count={count}")

        return {
                'reviews': reviews,
                'count': count,
                'rating': 5,
            }
