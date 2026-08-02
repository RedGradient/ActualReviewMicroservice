import json
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from django.test import TestCase
from requests import HTTPError

from common_parser.models import Branch, BranchPlatform, Organization, Review
from common_parser.parsers.twogis.helpers import _build_api_url, firm_id_from_url
from common_parser.parsers.twogis.parser import (
    TwoGisParseError,
    create_2gis_reviews,
    fetch_new_reviews,
    parse,
)
from common_parser.parsers.twogis.to_reviews import convert_2gis_reviews_to_model_data
from common_parser.tests.twogis.helpers import (
    FakeGetReviews,
    make_reviews_page,
    twogis_api_response,
)
from common_parser.types import ReviewsBundle


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
    @patch("common_parser.parsers.twogis.parser.fetch_new_reviews")
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
        mock_fetch.assert_called_once_with("12345", branch_platform, limit=50)
        mock_create_review.assert_called_once()
        mock_get_branch_platform.assert_called_once()


class FetchNewReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.fixture = json.loads(twogis_api_response())
        cls.reviews = cls.fixture["reviews"]

    @classmethod
    def _make_review(cls, index: int) -> dict:
        return cls.reviews[index]

    @classmethod
    def _make_branch_platform(cls, *, inn: str = "123456789012") -> BranchPlatform:
        organization = Organization.objects.create(inn=inn, name="Test Org")
        branch = Branch.objects.create(organization=organization, address="Test address")
        return BranchPlatform.objects.create(
            branch=branch,
            provider="2gis",
            url="https://2gis.ru/firm/12345",
        )

    @staticmethod
    def _save_2gis_review(branch_platform: BranchPlatform, review: dict) -> None:
        Review.objects.create(
            branch_platform=branch_platform,
            external_id=review["id"],
            author=review["user"]["name"],
            content=review["text"],
            rating=review["rating"],
            published_date=datetime(2026, 1, 1),
        )

    def test_returns_all_when_db_empty(self) -> None:
        branch_platform = self._make_branch_platform()
        get_reviews_page = FakeGetReviews([make_reviews_page(self.reviews, count=495)])

        bundle = fetch_new_reviews(
            "12345",
            branch_platform,
            limit=50,
            get_reviews_page=get_reviews_page,
        )

        self.assertEqual(len(bundle.reviews), len(self.reviews))
        self.assertEqual(bundle.rating, 4.8)
        self.assertEqual(bundle.count, 495)
        self.assertEqual(get_reviews_page.calls, [("12345", 50, 0)])

    def test_mixed_page_returns_only_new_before_stop(self) -> None:
        branch_platform = self._make_branch_platform()
        page_reviews = self.reviews[:3]
        self._save_2gis_review(branch_platform, page_reviews[2])

        bundle = fetch_new_reviews(
            "12345",
            branch_platform,
            limit=10,
            get_reviews_page=FakeGetReviews([make_reviews_page(page_reviews, count=3)]),
        )

        self.assertEqual(len(bundle.reviews), 2)
        self.assertEqual(bundle.reviews[0]["id"], page_reviews[0]["id"])
        self.assertEqual(bundle.reviews[1]["id"], page_reviews[1]["id"])

    def test_pagination_stops_on_second_page(self) -> None:
        branch_platform = self._make_branch_platform()
        page_one = self.reviews[:3]
        page_two = self.reviews[3:6]
        self._save_2gis_review(branch_platform, page_two[0])

        get_reviews_page = FakeGetReviews(
            [
                make_reviews_page(page_one, count=6),
                make_reviews_page(page_two, count=6),
            ]
        )

        bundle = fetch_new_reviews(
            "12345",
            branch_platform,
            limit=3,
            get_reviews_page=get_reviews_page,
        )

        self.assertEqual(len(bundle.reviews), 3)
        self.assertEqual(get_reviews_page.calls, [("12345", 3, 0), ("12345", 3, 3)])
        self.assertEqual(bundle.reviews[-1]["id"], page_one[-1]["id"])

    def test_does_not_stop_on_other_branch(self) -> None:
        other_platform = self._make_branch_platform(inn="987654321098")
        self._save_2gis_review(other_platform, self.reviews[0])

        branch_platform = self._make_branch_platform()
        bundle = fetch_new_reviews(
            "12345",
            branch_platform,
            limit=50,
            get_reviews_page=FakeGetReviews([make_reviews_page(self.reviews, count=495)]),
        )

        self.assertEqual(len(bundle.reviews), len(self.reviews))

    def test_stops_on_existing_external_id(self) -> None:
        branch_platform = self._make_branch_platform()
        existing = self.reviews[0]
        Review.objects.create(
            branch_platform=branch_platform,
            external_id=existing["id"],
            author=existing["user"]["name"],
            content=existing["text"],
            rating=existing["rating"],
            published_date=datetime(2026, 1, 1),
        )

        bundle = fetch_new_reviews(
            "12345",
            branch_platform,
            limit=50,
            get_reviews_page=FakeGetReviews([make_reviews_page(self.reviews, count=495)]),
        )

        self.assertEqual(bundle.reviews, [])

    def test_preserves_meta_from_first_page(self) -> None:
        branch_platform = self._make_branch_platform()

        bundle = fetch_new_reviews(
            "12345",
            branch_platform,
            limit=50,
            get_reviews_page=FakeGetReviews([make_reviews_page(self.reviews[:1], count=495)]),
        )

        self.assertEqual(bundle.rating, 4.8)
        self.assertEqual(bundle.count, 495)

    @unittest.skip("Пока не уверен, что это окончательный контракт")
    def test_http_error_propagates(self) -> None:
        branch_platform = self._make_branch_platform()
        response = Mock()
        response.raise_for_status = Mock(side_effect=HTTPError("502"))

        def broken_get_reviews_page(firm_id, limit, offset=0):
            return response

        with self.assertRaises(HTTPError):
            fetch_new_reviews(
                "12345",
                branch_platform,
                get_reviews_page=broken_get_reviews_page,
            )
