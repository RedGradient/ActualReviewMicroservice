import os
from datetime import datetime

import isodate
from dotenv import load_dotenv
from googleapiclient.discovery import build

from common_parser.tools.create_objects import create_video, get_or_create_playlist

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=API_KEY)


def get_playlist_videos(playlist_id: int) -> dict:
    """получаем видио из плейлиста"""
    videos = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet", playlistId=playlist_id, maxResults=50, pageToken=next_page_token
        )
        response = request.execute()

        video_ids = [item["snippet"]["resourceId"]["videoId"] for item in response["items"]]

        video_response = youtube.videos().list(part="contentDetails", id=",".join(video_ids)).execute()

        durations = {
            vid["id"]: isodate.parse_duration(vid["contentDetails"]["duration"]).total_seconds()
            for vid in video_response["items"]
        }

        for item in response["items"]:
            video = item["snippet"]
            video_id = video["resourceId"]["videoId"]

            thumbnails = video["thumbnails"]
            thumbnail_keys = ["maxres", "standard", "high", "medium", "default"]
            best_thumbnail_key = next((key for key in thumbnail_keys if key in thumbnails), None)
            best_thumbnail = thumbnails.get(best_thumbnail_key, {})

            videos.append(
                {
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": video["title"],
                    "author": video["channelTitle"],
                    "date": datetime.strptime(video["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"),
                    "preview": best_thumbnail.get("url", ""),
                    "duration": durations.get(video_id, 0),
                }
            )

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def get_playlist_data(playlist_url: str) -> dict:
    playlist_id = playlist_url.split("list=")[1].split("&")[0]

    playlist_videos = get_playlist_videos(playlist_id)

    playlist_data = {
        "url": playlist_url,
        "title": youtube.playlists().list(part="snippet", id=playlist_id).execute()["items"][0]["snippet"]["title"],
        "count": len(playlist_videos),
        "viedos": playlist_videos,
        "provider": "youtube",
        "parse_date": datetime.now(),
    }

    return playlist_data


def parse_youtube_videos(url: str) -> tuple[int, int]:
    data = get_playlist_data(url)

    viedos = data.pop("viedos")

    playlist = get_or_create_playlist(data)

    for video in viedos:
        video["playlist"] = playlist.id

    cnt = 0

    for video in viedos:
        if create_video(video):
            cnt += 1

    return (len(viedos), cnt)
