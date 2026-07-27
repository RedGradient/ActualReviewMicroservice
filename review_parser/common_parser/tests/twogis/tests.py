import json
from unittest.mock import Mock, patch

from django.test import TestCase
from requests import HTTPError

from common_parser.types import ReviewsBundle
from common_parser.tests.twogis.helpers import (
    FakeGetReviews,
    fake_get_reviews_page,
    make_reviews_page,
    twogis_api_response,
)
from common_parser.parsers.twogis.parser import (
    TwoGisParseError,
    _build_api_url,
    create_2gis_reviews,
    fetch_all_reviews,
    firm_id_from_url,
    parse,
)
from common_parser.parsers.twogis.to_reviews import convert_2gis_reviews_to_model_data


class ParseTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_response = twogis_api_response()

    def test_parse_ok(self) -> None:
        bundle = parse(response_text=self.api_response)

        self.assertIsInstance(bundle, ReviewsBundle)
        self.assertEqual(bundle.rating, 4.8)
        self.assertEqual(bundle.count, 495)
        self.assertEqual(len(bundle.reviews), 10)
        self.assertEqual(bundle.reviews[0]["id"], "260869980")

    def test_parse_invalid_json(self) -> None:
        with self.assertRaises(TwoGisParseError):
            parse("{not-json")

    def test_parse_missing_meta(self) -> None:
        payload = json.dumps({"reviews": []})

        with self.assertRaises(TwoGisParseError):
            parse(payload)

    def test_parse_empty_reviews(self) -> None:
        payload = json.dumps(
            {
                "meta": {
                    "branch_rating": 0,
                    "branch_reviews_count": 0,
                    "total_count": 0,
                },
                "reviews": [],
            }
        )

        bundle = parse(payload)

        self.assertEqual(bundle.rating, 0)
        self.assertEqual(bundle.count, 0)
        self.assertEqual(bundle.reviews, [])


class FirmIdFromUrlTests(TestCase):
    def test_ok(self) -> None:
        firm = firm_id_from_url("https://2gis.ru/firm/12345/reviews")
        self.assertEqual(firm, "12345")

    def test_missing_firm_segment(self) -> None:
        self.assertIsNone(firm_id_from_url("https://2gis.ru/org/12345"))


class BuildApiUrlTests(TestCase):
    def test_contains_firm_limit_offset_and_key(self) -> None:
        url = _build_api_url("70000001041081959", limit=20, offset=40)

        self.assertIn("/branches/70000001041081959/reviews", url)
        self.assertIn("limit=20", url)
        self.assertIn("offset=40", url)
        self.assertIn("branch_reviews_count", url)


class FetchAllReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_response = twogis_api_response()

    def test_single_page(self) -> None:
        bundle = fetch_all_reviews(
            firm_id="12345",
            limit=20,
            get_reviews_page=fake_get_reviews_page(self.api_response),
        )

        self.assertEqual(bundle.rating, 4.8)
        self.assertEqual(bundle.count, 495)
        self.assertEqual(len(bundle.reviews), 10)

    def test_pagination(self) -> None:
        fixture = json.loads(self.api_response)
        reviews = fixture["reviews"]

        get_reviews_page = FakeGetReviews(
            [
                make_reviews_page(reviews[:5], count=8),
                make_reviews_page(reviews[5:8], count=8),
            ]
        )

        bundle = fetch_all_reviews(
            firm_id="12345",
            limit=5,
            get_reviews_page=get_reviews_page,
        )

        self.assertEqual(get_reviews_page.calls, [("12345", 5, 0), ("12345", 5, 5)])
        self.assertEqual(len(bundle.reviews), 8)
        self.assertEqual(bundle.count, 8)

    def test_stops_when_count_reached(self) -> None:
        reviews = [{"id": str(i), "text": "ok", "rating": 5} for i in range(50)]

        get_reviews_page = FakeGetReviews(
            [
                make_reviews_page(reviews, count=50),
                make_reviews_page([], count=50),
            ]
        )

        bundle = fetch_all_reviews(
            firm_id="12345",
            limit=50,
            get_reviews_page=get_reviews_page,
        )

        self.assertEqual(len(bundle.reviews), 50)
        self.assertEqual(get_reviews_page.calls, [("12345", 50, 0)])

    def test_empty_reviews(self) -> None:
        payload = json.dumps(make_reviews_page([], count=0, rating=0))

        bundle = fetch_all_reviews(
            firm_id="12345",
            get_reviews_page=fake_get_reviews_page(payload),
        )

        self.assertEqual(bundle.reviews, [])
        self.assertEqual(bundle.count, 0)

    def test_http_error_propagates(self) -> None:
        response = Mock()
        response.raise_for_status = Mock(side_effect=HTTPError("502"))

        def broken_get_reviews_page(firm_id, limit, offset=0):
            return response

        with self.assertRaises(HTTPError):
            fetch_all_reviews(
                firm_id="12345",
                get_reviews_page=broken_get_reviews_page,
            )


class Convert2gisReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.review_data = json.loads(twogis_api_response())["reviews"][0]

    def test_convert_maps_main_fields(self) -> None:
        branch_platform = Mock()
        branch_platform.id = 1
        url = "https://2gis.ru/firm/12345"

        data = convert_2gis_reviews_to_model_data(
            branch_platform=branch_platform,
            review_data=self.review_data,
            url=url,
        )

        self.assertEqual(data["branch_platform"], branch_platform)
        self.assertEqual(data["author"], self.review_data["user"]["name"])
        self.assertEqual(data["rating"], self.review_data["rating"])
        self.assertEqual(data["content"], self.review_data["text"])
        self.assertIn("/tab/reviews/review/", data["review_url"])
        self.assertNotIn("provider", data)


class Create2gisReviewsTests(TestCase):
    def test_invalid_url_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_2gis_reviews(url="https://example.com/no-firm", inn="123456789012")

    @patch("common_parser.parsers.twogis.parser.create_review", return_value=True)
    @patch("common_parser.parsers.twogis.parser.get_or_create_branch_platform")
    @patch("common_parser.parsers.twogis.parser.get_or_create_Organization")
    @patch("common_parser.parsers.twogis.parser.fetch_all_reviews")
    def test_creates_reviews_from_bundle(
        self,
        mock_fetch,
        mock_get_org,
        mock_get_branch_platform,
        mock_create_review,
    ) -> None:
        mock_fetch.return_value = ReviewsBundle(
            reviews=[{"id": "1", "text": "hi", "rating": 5, "user": {"name": "Ann"}}],
            count=1,
            rating=4.5,
        )
        branch_platform = Mock()
        mock_get_branch_platform.return_value = branch_platform

        fetched, created = create_2gis_reviews(
            url="https://2gis.ru/firm/12345",
            inn="123456789012",
            address="Test address",
        )

        self.assertEqual(fetched, 1)
        self.assertEqual(created, 1)
        mock_fetch.assert_called_once_with("12345", limit=50)
        mock_create_review.assert_called_once()
        mock_get_branch_platform.assert_called_once()
