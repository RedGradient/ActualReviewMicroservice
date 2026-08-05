from unittest.mock import Mock, patch

import bs4
from django.test import TestCase
from requests import HTTPError

from common_parser.models import Branch, BranchPlatform, Organization, Review
from common_parser.parsers.vlru.helpers import get_company_from_url, get_company_rating, get_company_review_count
from common_parser.parsers.vlru.parser import (
    create_vlru_reviews,
    fetch_new_reviews,
    parse_vlru_reviews,
)
from common_parser.tests.vlru.helpers import (
    FakeVLClient,
    make_response,
    vlru_comments_second_page,
    vlru_comments_single_html,
    vlru_company_main_page_html,
    vlru_thread_first_page,
    vlru_thread_last_page,
)
from common_parser.tools.hash import normalize_and_hash
from common_parser.types import ReviewsBundle


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
        self.assertTrue(review["author"])
        self.assertGreater(review["rating"], 0)
        self.assertTrue(review["content"])

    def test_skips_replies(self) -> None:
        full_count = len(parse_vlru_reviews(self.thread_html))
        single_count = len(parse_vlru_reviews(self.html))

        self.assertGreater(full_count, single_count)

    def test_empty_html(self) -> None:
        self.assertEqual(parse_vlru_reviews("<ul id='CommentsList'></ul>"), [])


class CreateVlruReviewsTests(TestCase):
    def test_invalid_url_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_vlru_reviews(url="https://www.vl.ru/", inn="123456789012")

    @patch("common_parser.parsers.vlru.parser._delete_overflow_reviews")
    @patch("common_parser.parsers.vlru.parser.create_review", return_value=True)
    @patch("common_parser.parsers.vlru.parser.get_or_create_branch_platform")
    @patch("common_parser.parsers.vlru.parser.get_or_create_Organization")
    @patch("common_parser.parsers.vlru.parser.fetch_new_reviews")
    def test_creates_reviews_from_bundle(
        self,
        mock_fetch,
        mock_get_org,
        mock_get_branch_platform,
        mock_create_review,
        mock_delete_overflow,
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
                }
            ],
            count=1,
            rating=5,
        )
        branch_platform = Mock()
        branch_platform.id = 1
        branch_platform.org_id = None
        mock_get_branch_platform.return_value = branch_platform

        fetched, created = create_vlru_reviews(
            url="https://www.vl.ru/trinity",
            inn="123456789012",
            address="Test address",
        )

        self.assertEqual(fetched, 1)
        self.assertEqual(created, 1)
        mock_fetch.assert_called_once()
        mock_create_review.assert_called_once()
        mock_get_branch_platform.assert_called_once()
        mock_delete_overflow.assert_called_once_with(1)


class FetchNewReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.first_page = vlru_thread_first_page()
        cls.second_page = vlru_comments_second_page()
        cls.last_page = vlru_thread_last_page()
        cls.page_one_reviews = parse_vlru_reviews(cls.first_page["data"]["content"])
        cls.page_two_reviews = parse_vlru_reviews(cls.second_page["data"]["content"])

    @classmethod
    def _make_branch_platform(cls, *, inn: str = "123456789012") -> BranchPlatform:
        organization = Organization.objects.create(inn=inn, name="Test Org")
        branch = Branch.objects.create(organization=organization, address="Test address")
        return BranchPlatform.objects.create(
            branch=branch,
            provider="vlru",
            url="https://www.vl.ru/trinity",
        )

    @staticmethod
    def _save_vlru_review(branch_platform: BranchPlatform, review: dict) -> None:
        Review.objects.create(
            branch_platform=branch_platform,
            external_id=review["external_id"],
            author=review["author"],
            content=review["content"],
            content_hash=normalize_and_hash(review["content"]),
            rating=str(review["rating"]),
            published_date=review["published_date"],
        )

    def test_returns_all_when_db_empty(self) -> None:
        branch_platform = self._make_branch_platform()
        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(len(bundle.reviews), len(self.page_one_reviews))
        self.assertEqual(bundle.rating, 0.8215)
        self.assertEqual(bundle.count, 309)
        self.assertEqual(client.company_pages_calls, ["trinity"])

    def test_stops_on_existing_external_id(self) -> None:
        branch_platform = self._make_branch_platform()
        existing = self.page_one_reviews[0]
        Review.objects.create(
            branch_platform=branch_platform,
            external_id=existing["external_id"],
            author=existing["author"],
            content=existing["content"],
            content_hash=normalize_and_hash(existing["content"]),
            rating=str(existing["rating"]),
            published_date=existing["published_date"],
        )

        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(bundle.reviews, [])

    def test_mixed_page_returns_only_new_before_stop(self) -> None:
        branch_platform = self._make_branch_platform()
        page_reviews = self.page_one_reviews[:3]
        self._save_vlru_review(branch_platform, page_reviews[2])

        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(len(bundle.reviews), 2)
        self.assertEqual(bundle.reviews[0]["author"], page_reviews[0]["author"])
        self.assertEqual(bundle.reviews[1]["author"], page_reviews[1]["author"])

    def test_pagination_stops_on_second_page(self) -> None:
        branch_platform = self._make_branch_platform()
        self._save_vlru_review(branch_platform, self.page_two_reviews[0])

        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.second_page, self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(len(bundle.reviews), len(self.page_one_reviews))
        self.assertEqual(len(client.comments_calls), 1)

    def test_stops_on_first_existing(self) -> None:
        branch_platform = self._make_branch_platform()
        self._save_vlru_review(branch_platform, self.page_one_reviews[0])

        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(bundle.reviews, [])
        self.assertEqual(bundle.rating, 0.8215)
        self.assertEqual(bundle.count, 309)

    def test_does_not_stop_on_other_branch(self) -> None:
        other_platform = self._make_branch_platform(inn="987654321098")
        self._save_vlru_review(other_platform, self.page_one_reviews[0])

        branch_platform = self._make_branch_platform()
        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(len(bundle.reviews), len(self.page_one_reviews))

    def test_preserves_meta_when_stops_early(self) -> None:
        branch_platform = self._make_branch_platform()
        self._save_vlru_review(branch_platform, self.page_one_reviews[0])

        client = FakeVLClient(
            thread_payload=self.first_page,
            comment_pages=[self.last_page],
        )

        bundle = fetch_new_reviews("trinity", branch_platform, client=client)

        self.assertEqual(bundle.rating, 0.8215)
        self.assertEqual(bundle.count, 309)

    def test_http_error_on_company_page_propagates(self) -> None:
        response = Mock()
        response.raise_for_status = Mock(side_effect=HTTPError("502"))

        class BrokenClient:
            def get_company_page(self, company: str):
                return response

        with self.assertRaises(HTTPError):
            fetch_new_reviews(
                "trinity",
                self._make_branch_platform(),
                client=BrokenClient(),
            )

    def test_http_error_on_thread_propagates(self) -> None:
        company_response = make_response(vlru_company_main_page_html())
        error_response = Mock()
        error_response.raise_for_status = Mock(side_effect=HTTPError("502"))

        class BrokenClient:
            def get_company_page(self, company: str):
                return company_response

            def get_thread(self, company: str):
                return error_response

        with self.assertRaises(HTTPError):
            fetch_new_reviews(
                "trinity",
                self._make_branch_platform(),
                client=BrokenClient(),
            )


class GetCompanyRatingTests(TestCase):
    def test_returns_rating_from_fixture(self) -> None:
        result = get_company_rating(vlru_company_main_page_html())

        self.assertIsNotNone(result)
        self.assertEqual(result, 0.8215)

    @patch("common_parser.parsers.vlru.helpers.BeautifulSoup")
    def test_returns_none_when_element_is_not_tag(self, mock_bs) -> None:
        mock_bs.return_value.find.return_value = "unexpected"

        self.assertIsNone(get_company_rating("<html></html>"))

    @patch("common_parser.parsers.vlru.helpers.BeautifulSoup")
    def test_returns_none_when_data_default_is_not_string(self, mock_bs) -> None:
        html = '<ul class="stars control" data-default="0,5"></ul>'
        soup = bs4.BeautifulSoup(html, "html.parser")
        rating_el = soup.find("ul")
        assert rating_el is not None

        with patch.object(rating_el, "get", return_value=42):
            mock_bs.return_value.find.return_value = rating_el
            self.assertIsNone(get_company_rating(html))

    def test_returns_none_when_data_default_is_not_numeric(self) -> None:
        html = '<ul class="stars control" data-default="n/a"></ul>'
        self.assertIsNone(get_company_rating(html))


class GetCompanyReviewCountTests(TestCase):
    def test_returns_count_from_fixture(self) -> None:
        result = get_company_review_count(vlru_company_main_page_html())

        self.assertIsNotNone(result)
        self.assertEqual(result, 309)

    @patch("common_parser.parsers.vlru.helpers.BeautifulSoup")
    def test_returns_none_when_comments_link_is_not_tag(self, mock_bs) -> None:
        mock_bs.return_value.find.return_value = "unexpected"
        self.assertIsNone(get_company_review_count("<html></html>"))

    def test_returns_none_when_link_text_has_no_digits(self) -> None:
        html = '<a href="#comments" class="hash-link">Отзывы</a>'
        self.assertIsNone(get_company_review_count(html))

    def test_returns_first_number_from_link_text(self) -> None:
        html = '<a href="#comments" class="hash-link">Всего отзывов: 309</a>'
        self.assertEqual(get_company_review_count(html), 309)
