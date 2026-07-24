import requests
from bs4 import BeautifulSoup
from .models import Review

def parse_google_reviews(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'lxml')
    reviews = []
    for div in soup.find_all('div', class_='review'):
        try:
            text = div.find('span').text.strip() if div.find('span') else None
            rating = float(div.find('meta', itemprop="ratingValue")['content']) if div.find('meta', itemprop="ratingValue") else None
            reviews.append((text, rating))
        except Exception as e:
            print(f'Ошибка при обработке отзыва: {e}')
    return reviews


def parse_yandex_reviews(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'lxml')
    reviews = []
    for div in soup.find_all('div', class_='comment__body'):
        try:
            text = div.find('p').text.strip() if div.find('p') else None
            rating = int(div.find('span', class_='rating__value').text.strip()) if div.find('span', class_='rating__value') else None
            reviews.append((text, rating))
        except Exception as e:
            print(f'Ошибка при обработке отзыва: {e}')
    return reviews