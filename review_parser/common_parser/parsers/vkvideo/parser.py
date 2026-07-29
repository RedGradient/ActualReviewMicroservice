import json
import re
from datetime import datetime

import requests
from loguru import logger
from playwright.sync_api import sync_playwright

from common_parser.tools.create_objects import create_video, get_or_create_playlist


def get_token(url: str) -> dict:
    """Получаем токен анонимного пользователя из запросов на странице без Selenium"""
    logger.info(f"VK token fetch started: url={url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Переменная для хранения токена
        token_data = {}

        # Функция для обработки запросов
        def handle_response(response):
            nonlocal token_data
            if "get_anonym_token" in response.url:
                try:
                    # Пытаемся получить JSON
                    try:
                        token_data = response.json()
                    except Exception:
                        # Если не JSON, пробуем текст
                        body = response.text()
                        try:
                            token_data = json.loads(body)
                        except Exception:
                            token_data = {}
                    logger.info(f"Token response received: {token_data}")
                except Exception as e:
                    logger.error(f"Error processing token response: {e}")

        # Подписываемся на события ответов
        page.on("response", handle_response)

        # Переходим на страницу
        page.goto(url, wait_until="networkidle", timeout=30000)

        # Ждем немного для загрузки всех запросов
        for _ in range(15):
            if token_data:
                break
            page.wait_for_timeout(1000)

        browser.close()

        return token_data


def parse_video_data(owner_id: int, album_id: int, token: str) -> dict:
    params = {
        "owner_id": owner_id,
        "album_id": album_id,
        "access_token": token,
        "v": "5.199",
        "count": 50,
        "extended": 1,
    }
    response = requests.get("https://api.vk.com/method/video.get", params=params)
    return response.json()


def parse_playlist_data(owner_id: int, album_id: int, token: str) -> dict:
    params = {
        "owner_id": owner_id,
        "album_id": album_id,
        "access_token": token,
        "v": "5.199",
    }
    response = requests.get("https://api.vk.com/method/video.getAlbumById", params=params)
    return response.json()


def get_video_data(data: dict, playlist: int, author: str) -> dict:
    """собираем видео для нашей модели"""
    scale = 0
    prew = ""
    for prewi in data.get("image"):
        width = int(prewi.get("width"))
        if scale < width:
            scale = width
            prew = prewi.get("url")

    print(prew)

    result = {
        "url": data.get("share_url"),
        "title": data.get("title"),
        "author": author,
        "date": datetime.fromtimestamp(data.get("date")),
        "preview": prew,
        "duration": data.get("duration"),
        "playlist": playlist,
    }

    return result


def get_ids(url: str) -> tuple[int, int]:
    """из url получаем id автора и id плейлиста"""
    pattern = r"(-?\d+)_(-?\d+)$"
    match = re.search(pattern, url)

    if match:
        group1 = match.group(1)
        group2 = match.group(2)
        print(f"group1: {group1}, group2: {group2}")
        return (int(group1), int(group2))


def parse_vk_videos(url: str) -> tuple[int, int]:
    token = get_token(url).get("data", {}).get("access_token", "")

    if token:
        author_id, playlist_id = get_ids(url)

        videos = parse_video_data(author_id, playlist_id, token)

        videos = videos.get("response")

        playlist = parse_playlist_data(author_id, playlist_id, token)

        playlist = playlist.get("response")

        playlist_data = {
            "title": playlist.get("title"),
            "count": playlist.get("count"),
            "url": url,
            "parse_date": datetime.now(),
            "provider": "vk",
        }

        playlist = get_or_create_playlist(playlist_data)

        cnt = 0

        author = videos.get("groups")[0].get("name")
        for video in videos.get("items"):
            if create_video(get_video_data(video, playlist.id, author)):
                cnt += 1
    else:
        raise ValueError("Ошибка: не удалось получить токен")

    return (len(videos), cnt)
