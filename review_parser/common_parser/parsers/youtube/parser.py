import time
from datetime import datetime
from typing import Any

import googleapiclient.discovery
import isodate
from googleapiclient.discovery import build
from loguru import logger

from common_parser.models import Playlist, Video
from common_parser.parsers.helpers import _delete_overflow_videos
from common_parser.tools.create_objects import create_video
from common_parser.types import ParseResult
from review_parser.settings import MAX_VIDEO_COUNT, YOUTUBE_API_KEY


class YoutubeClient:
    def __init__(self, youtube: googleapiclient.discovery.Resource):
        self._youtube = youtube

    def get_playlist_videos(self, playlist_id: str) -> list[dict[str, Any]]:
        """Возвращает список метаданных видео из плейлиста."""

        logger.debug("fetch started playlist_id={} limit={}", playlist_id, MAX_VIDEO_COUNT)

        videos: list[dict[str, Any]] = []
        next_page_token = None

        while True:
            if len(videos) >= MAX_VIDEO_COUNT:
                break

            playlist_response = (
                self._youtube.playlistItems()
                .list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=min(50, MAX_VIDEO_COUNT - len(videos)),
                    pageToken=next_page_token,
                )
                .execute()
            )

            if not (items := playlist_response.get("items", [])):
                break

            logger.debug(
                "fetch page playlist_id={} page_token={} batch={} total={}",
                playlist_id,
                next_page_token,
                len(items),
                len(videos) + len(items),
            )

            video_ids = [item["contentDetails"]["videoId"] for item in items]

            video_response = self._youtube.videos().list(part="contentDetails", id=",".join(video_ids)).execute()

            durations = {
                video["id"]: isodate.parse_duration(video["contentDetails"]["duration"]).total_seconds()
                for video in video_response.get("items", [])
            }

            for item in items:
                snippet = item["snippet"]
                video_id = item["contentDetails"]["videoId"]

                thumbnails = snippet.get("thumbnails", {})
                thumbnail_keys = ["maxres", "standard", "high", "medium", "default"]
                best_thumbnail_key = next((key for key in thumbnail_keys if key in thumbnails), None)
                best_thumbnail = thumbnails.get(best_thumbnail_key, {}) if best_thumbnail_key else {}

                videos.append(
                    {
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "title": snippet["title"],
                        "author": snippet["channelTitle"],
                        "published_date": datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
                        "preview": best_thumbnail.get("url", ""),
                        "duration": durations.get(video_id, 0),
                    }
                )

                if len(videos) >= MAX_VIDEO_COUNT:
                    break

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break

        logger.info("fetch done playlist_id={} videos={}", playlist_id, len(videos))
        return videos

    def get_playlist_data(self, playlist_url: str) -> dict:
        playlist_id = playlist_url.split("list=")[1].split("&")[0]

        logger.info("started url={} playlist_id={}", playlist_url, playlist_id)

        playlist_response = self._youtube.playlists().list(part="snippet", id=playlist_id).execute()
        items = playlist_response.get("items", [])
        if not items:
            logger.error("playlist not found playlist_id={}", playlist_id)
            raise ValueError(f"Playlist not found: {playlist_id}")

        snippet = items[0]["snippet"]
        logger.debug(
            "playlist metadata title={} author={}",
            snippet.get("title"),
            snippet.get("channelTitle"),
        )
        playlist_videos = self.get_playlist_videos(playlist_id)

        return {
            "url": playlist_url,
            "author": snippet.get("channelTitle", ""),
            "title": snippet.get("title", ""),
            "count": len(playlist_videos),
            "videos": playlist_videos,
            "provider": "youtube",
            "parse_date": datetime.now(),
        }


def create_youtube_videos(playlist_url: str, youtube: YoutubeClient) -> ParseResult:
    started_at = time.monotonic()
    logger.info("started url={}", playlist_url)

    data = youtube.get_playlist_data(playlist_url)
    videos = data.pop("videos")
    url = data.pop("url")

    playlist, _ = Playlist.objects.update_or_create(url=url, defaults=data)

    new_videos = []
    for video in videos:
        if not Video.objects.filter(url=video["url"], playlist_id=playlist.id).exists():
            new_videos.append(video)

    for video in new_videos:
        video["playlist"] = playlist.id

    created = 0
    skipped = 0
    for video in new_videos:
        if create_video(video):
            created += 1
        else:
            skipped += 1

    _delete_overflow_videos(playlist.id)

    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "finished parsed={} created={} skipped={} duration_ms={}",
        len(videos),
        created,
        skipped,
        duration_ms,
    )

    return ParseResult(parsed=len(videos), created=created)


class YoutubeParser:
    provider = "youtube"

    def run(
        self,
        playlist_url: str,
    ) -> ParseResult:
        with logger.contextualize(provider=self.provider):
            youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
            client = YoutubeClient(youtube=youtube)
            return create_youtube_videos(playlist_url, client)
