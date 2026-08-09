from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from common_parser.models import Playlist, Video
from common_parser.parsers.youtube.parser import YoutubeClient, create_youtube_videos


def _make_playlist_item(
    video_id: str,
    title: str,
    *,
    published_at: str = "2023-08-20T03:14:07Z",
    channel_title: str = "Test Channel",
) -> dict:
    return {
        "snippet": {
            "title": title,
            "channelTitle": channel_title,
            "publishedAt": published_at,
            "thumbnails": {
                "high": {"url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"},
            },
        },
        "contentDetails": {"videoId": video_id},
    }


def _make_video_duration_item(video_id: str, duration: str = "PT10M30S") -> dict:
    return {
        "id": video_id,
        "contentDetails": {"duration": duration},
    }


class YoutubeClientTests(TestCase):
    def _get_youtube_mock(self) -> MagicMock:
        youtube_mock = MagicMock()

        playlist_response = {
            "items": [
                _make_playlist_item("abc123", "Test Video"),
                _make_playlist_item("def456", "Test Video 2", published_at="2023-09-01T12:00:00Z"),
            ],
        }

        video_response = {
            "items": [
                _make_video_duration_item("abc123", "PT10M30S"),
                _make_video_duration_item("def456", "PT5M"),
            ],
        }

        playlist_meta_response = {
            "items": [
                {
                    "snippet": {
                        "title": "Test Playlist",
                        "channelTitle": "Test Channel",
                    }
                }
            ],
        }

        youtube_mock.playlistItems.return_value.list.return_value.execute.return_value = playlist_response
        youtube_mock.videos.return_value.list.return_value.execute.return_value = video_response
        youtube_mock.playlists.return_value.list.return_value.execute.return_value = playlist_meta_response

        return youtube_mock

    def test_get_playlist_videos(self):
        youtube = self._get_youtube_mock()
        client = YoutubeClient(youtube=youtube)

        videos = client.get_playlist_videos("some_playlist_id")

        self.assertEqual(len(videos), 2)

        video = videos[0]
        self.assertEqual(video.get("title"), "Test Video")
        self.assertEqual(video.get("author"), "Test Channel")
        self.assertEqual(video.get("url"), "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(video.get("preview"), "https://i.ytimg.com/vi/abc123/hqdefault.jpg")
        self.assertEqual(video.get("duration"), 630.0)
        self.assertIsInstance(video.get("published_date"), datetime)

        video_2 = videos[1]
        self.assertEqual(video_2.get("title"), "Test Video 2")
        self.assertEqual(video_2.get("url"), "https://www.youtube.com/watch?v=def456")
        self.assertEqual(video_2.get("preview"), "https://i.ytimg.com/vi/def456/hqdefault.jpg")
        self.assertEqual(video_2.get("duration"), 300.0)

    @patch("common_parser.parsers.youtube.parser.MAX_VIDEO_COUNT", 1)
    def test_get_playlist_videos_respects_max_video_count(self):
        youtube = self._get_youtube_mock()
        client = YoutubeClient(youtube=youtube)

        videos = client.get_playlist_videos("some_playlist_id")

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].get("url"), "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(videos[0].get("title"), "Test Video")

        youtube.playlistItems.return_value.list.assert_called_once_with(
            part="snippet,contentDetails",
            playlistId="some_playlist_id",
            maxResults=1,
            pageToken=None,
        )

    @patch("common_parser.parsers.youtube.parser.MAX_VIDEO_COUNT", 20)
    def test_get_playlist_videos_paging(self):
        youtube = MagicMock()

        page_1_playlist_response = {
            "items": [_make_playlist_item("abc123", "Test Video")],
            "nextPageToken": "page2",
        }
        page_2_playlist_response = {
            "items": [_make_playlist_item("def456", "Test Video 2", published_at="2023-09-01T12:00:00Z")],
        }

        page_1_video_response = {"items": [_make_video_duration_item("abc123", "PT10M30S")]}
        page_2_video_response = {"items": [_make_video_duration_item("def456", "PT5M")]}

        youtube.playlistItems.return_value.list.return_value.execute.side_effect = [
            page_1_playlist_response,
            page_2_playlist_response,
        ]
        youtube.videos.return_value.list.return_value.execute.side_effect = [
            page_1_video_response,
            page_2_video_response,
        ]

        client = YoutubeClient(youtube=youtube)
        videos = client.get_playlist_videos("some_playlist_id")

        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0].get("url"), "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(videos[1].get("url"), "https://www.youtube.com/watch?v=def456")

        list_mock = youtube.playlistItems.return_value.list
        self.assertEqual(list_mock.call_count, 2)
        list_mock.assert_any_call(
            part="snippet,contentDetails",
            playlistId="some_playlist_id",
            maxResults=20,
            pageToken=None,  # Запрашивает первую страницу
        )
        list_mock.assert_any_call(
            part="snippet,contentDetails",
            playlistId="some_playlist_id",
            maxResults=19,
            pageToken="page2",  # Запрашивает ВТОРУЮ страницу
        )

    def test_get_playlist_data(self):
        playlist_url = "https://www.youtube.com/playlist?list=PLtest123"
        youtube = self._get_youtube_mock()
        client = YoutubeClient(youtube=youtube)

        data = client.get_playlist_data(playlist_url)

        self.assertEqual(data.get("url"), playlist_url)
        self.assertEqual(data.get("author"), "Test Channel")
        self.assertEqual(data.get("title"), "Test Playlist")
        self.assertEqual(data.get("count"), 2)
        self.assertEqual(data.get("provider"), "youtube")
        self.assertIsInstance(data.get("parse_date"), datetime)

        videos = data.get("videos")
        self.assertIsInstance(videos, list)
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0].get("url"), "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(videos[1].get("url"), "https://www.youtube.com/watch?v=def456")

        youtube.playlists.return_value.list.assert_called_once_with(part="snippet", id="PLtest123")


class CreateYoutubeVideosTests(TestCase):
    def setUp(self):
        Video.objects.all().delete()
        Playlist.objects.all().delete()

    def _get_youtube_client_mock(self, playlist_url: str | None = None) -> MagicMock:
        if playlist_url is None:
            playlist_url = "https://www.youtube.com/playlist?list=PLtest123"

        youtube_client_mock = MagicMock()
        youtube_client_mock.get_playlist_data.return_value = {
            "url": playlist_url,
            "author": "Test Channel",
            "title": "Test Playlist",
            "count": 2,
            "videos": [
                {
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Test Video",
                    "author": "Test Channel",
                    "published_date": datetime(2023, 8, 20, 3, 14, 7),
                    "preview": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
                    "duration": 630.0,
                },
                {
                    "url": "https://www.youtube.com/watch?v=def456",
                    "title": "Test Video 2",
                    "author": "Test Channel",
                    "published_date": datetime(2023, 9, 1, 12, 0, 0),
                    "preview": "https://i.ytimg.com/vi/def456/hqdefault.jpg",
                    "duration": 300.0,
                },
            ],
            "provider": "youtube",
            "parse_date": datetime.now(),
        }

        return youtube_client_mock

    def test_create_youtube_videos(self):
        youtube_client_mock = self._get_youtube_client_mock()

        parse_result = create_youtube_videos(
            playlist_url="https://www.youtube.com/playlist?list=PLtest123", youtube=youtube_client_mock
        )

        self.assertEqual(parse_result.parsed, 2)
        self.assertEqual(parse_result.created, 2)

        self.assertEqual(Playlist.objects.count(), 1)
        self.assertEqual(Video.objects.count(), 2)

    @patch("common_parser.parsers.helpers.MAX_VIDEO_COUNT", 2)
    def test_create_youtube_videos_removes_old(self):
        playlist_url = "https://www.youtube.com/playlist?list=PLtest123"
        playlist = Playlist.objects.create(
            url=playlist_url,
            title="Old Playlist",
            author="Test Channel",
            provider="youtube",
        )
        Video.objects.create(
            playlist=playlist,
            url="https://www.youtube.com/watch?v=old111",
            title="Oldest Video",
            published_date=datetime(2023, 1, 1, 0, 0, 0),
            duration=100,
        )
        Video.objects.create(
            playlist=playlist,
            url="https://www.youtube.com/watch?v=abc123",
            title="Existing Video",
            published_date=datetime(2023, 8, 20, 3, 14, 7),
            duration=630,
        )

        parse_result = create_youtube_videos(
            playlist_url=playlist_url,
            youtube=self._get_youtube_client_mock(),
        )

        self.assertEqual(parse_result.parsed, 2)
        self.assertEqual(parse_result.created, 1)

        playlist_videos = Video.objects.filter(playlist=playlist)
        self.assertEqual(playlist_videos.count(), 2)

        self.assertFalse(playlist_videos.filter(url="https://www.youtube.com/watch?v=old111").exists())

        self.assertTrue(playlist_videos.filter(url="https://www.youtube.com/watch?v=abc123").exists())
        self.assertTrue(playlist_videos.filter(url="https://www.youtube.com/watch?v=def456").exists())
