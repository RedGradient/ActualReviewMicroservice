import json
from unittest.mock import Mock, patch

from django.test import TestCase
from requests import HTTPError

from common_parser.types import ReviewsBundle
from vl_parser.fixtures import (
    vlru_avg_history,
    vlru_avg_history_low,
    vlru_comments_second_page,
    vlru_comments_single_html,
    vlru_thread_first_page,
    vlru_thread_last_page,
)
from vl_parser.test_doubles import FakeVLClient, make_json_response
from vl_parser.tools.parser import (
    _apply_avg_rating_from_history,
    create_vlru_reviews,
    fetch_all_reviews,
    get_company_from_url,
    parse_vlru_reviews,
)


class GetCompanyFromUrlTests(TestCase):
    def test_ok(self) -> None:
        self.assertEqual(get_company_from_url("https://www.vl.ru/trinity"), "trinity")

    def test_missing_slug(self) -> None:
        self.assertIsNone(get_company_from_url("https://www.vl.ru/"))


class ParseVlruReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.html = vlru_comments_single_html()
        cls.thread_html = vlru_thread_first_page()["data"]["content"]

    def test_parse_single_fixture(self) -> None:
        reviews = parse_vlru_reviews(self.html)

        self.assertEqual(len(reviews), 1)
        review = reviews[0]
        self.assertEqual(review["provider"], "vlru")
        self.assertTrue(review["author"])
        self.assertGreater(review["rating"], 0)
        self.assertTrue(review["content"])

    def test_skips_replies(self) -> None:
        full_count = len(parse_vlru_reviews(self.thread_html))
        single_count = len(parse_vlru_reviews(self.html))

        self.assertGreater(full_count, single_count)

    def test_empty_html(self) -> None:
        self.assertEqual(parse_vlru_reviews("<ul id='CommentsList'></ul>"), [])


class FetchAllReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.first_page = vlru_thread_first_page()
        cls.second_page = vlru_comments_second_page()
        cls.last_page = vlru_thread_last_page()

    def test_single_page_when_no_pagination(self) -> None:
        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_all_reviews("trinity", client=client)

        self.assertIsInstance(bundle, ReviewsBundle)
        self.assertEqual(client.thread_calls, ["trinity"])
        self.assertEqual(len(client.comments_calls), 1)
        self.assertGreater(bundle.count, 0)
        self.assertEqual(bundle.count, len(bundle.reviews))

    def test_pagination(self) -> None:
        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.second_page, self.last_page],
        )

        bundle = fetch_all_reviews("trinity", client=client)

        first_count = len(parse_vlru_reviews(self.first_page["data"]["content"]))
        second_count = len(parse_vlru_reviews(self.second_page["data"]["content"]))
        self.assertEqual(len(client.comments_calls), 2)
        self.assertEqual(bundle.count, first_count + second_count)

    def test_http_error_propagates(self) -> None:
        response = Mock()
        response.raise_for_status = Mock(side_effect=HTTPError("502"))

        class BrokenClient:
            def get_thread(self, company: str):
                return response

        with self.assertRaises(HTTPError):
            fetch_all_reviews("trinity", client=BrokenClient())


class ApplyAvgRatingTests(TestCase):
    def test_sets_avg_from_first_history_value(self) -> None:
        branch = Mock()
        response = make_json_response(vlru_avg_history())

        _apply_avg_rating_from_history(branch, response)

        self.assertEqual(branch.vlru_review_avg, 4.0)

    def test_clamps_low_avg_to_four(self) -> None:
        branch = Mock()
        response = make_json_response(vlru_avg_history_low())

        _apply_avg_rating_from_history(branch, response)

        self.assertEqual(branch.vlru_review_avg, 4)


class CreateVlruReviewsTests(TestCase):
    def test_invalid_url_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_vlru_reviews(url="https://www.vl.ru/", inn="123456789012")

    @patch("vl_parser.tools.parser.create_review", return_value=True)
    @patch("vl_parser.tools.parser.get_or_create_Branch")
    @patch("vl_parser.tools.parser.get_or_create_Organization")
    @patch("vl_parser.tools.parser.fetch_all_reviews")
    def test_creates_reviews_from_bundle(
        self,
        mock_fetch,
        mock_get_org,
        mock_get_branch,
        mock_create_review,
    ) -> None:
        mock_fetch.return_value = ReviewsBundle(
            reviews=[
                {
                    "author": "Ann",
                    "avatar": None,
                    "video": None,
                    "photos": "",
                    "published_date": Mock(),
                    "rating": 5,
                    "content": "ok",
                    "provider": "vlru",
                }
            ],
            count=1,
            rating=5,
        )
        branch = Mock()
        branch.vlru_org_id = None
        branch.save = Mock()
        mock_get_branch.return_value = branch

        fetched, created = create_vlru_reviews(
            url="https://www.vl.ru/trinity",
            inn="123456789012",
            address="Test address",
        )

        self.assertEqual(fetched, 1)
        self.assertEqual(created, 1)
        mock_fetch.assert_called_once()
        mock_create_review.assert_called_once()
        branch.save.assert_called()
