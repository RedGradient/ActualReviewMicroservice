from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase

from common_parser.models import Branch, BranchPlatform, Organization, Review
from common_parser.parsers.helpers import _delete_overflow_reviews

MAX_REVIEWS_UNDER_TEST = 3


class DeleteOverflowReviewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.max_reviews_patcher = patch(
            "common_parser.parsers.helpers.MAX_REVIEWS",
            MAX_REVIEWS_UNDER_TEST,
        )
        cls.max_reviews_patcher.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.max_reviews_patcher.stop()
        super().tearDownClass()

    @staticmethod
    def _make_branch_platform(*, inn: str = "123456789012", provider: str = "2gis") -> BranchPlatform:
        organization = Organization.objects.create(inn=inn, name="Test Org")
        branch = Branch.objects.create(organization=organization, address="Test address")
        return BranchPlatform.objects.create(
            branch=branch,
            provider=provider,
            url="https://example.com/firm/1",
        )

    @staticmethod
    def _create_reviews(branch_platform: BranchPlatform, count: int) -> None:
        base_date = datetime(2026, 1, 1)
        for index in range(count):
            Review.objects.create(
                branch_platform=branch_platform,
                author=f"Author {index}",
                content=f"Content {index}",
                content_hash=f"hash-{index}",
                rating="5",
                published_date=base_date + timedelta(days=index),
            )

    def test_does_nothing_when_under_limit(self) -> None:
        branch_platform = self._make_branch_platform()
        self._create_reviews(branch_platform, count=2)

        _delete_overflow_reviews(branch_platform.id)

        self.assertEqual(branch_platform.reviews.count(), 2)

    def test_does_nothing_when_at_limit(self) -> None:
        branch_platform = self._make_branch_platform()
        self._create_reviews(branch_platform, count=MAX_REVIEWS_UNDER_TEST)

        _delete_overflow_reviews(branch_platform.id)

        self.assertEqual(branch_platform.reviews.count(), MAX_REVIEWS_UNDER_TEST)

    def test_deletes_oldest_reviews_when_overflow(self) -> None:
        branch_platform = self._make_branch_platform()
        self._create_reviews(branch_platform, count=5)

        _delete_overflow_reviews(branch_platform.id)

        self.assertEqual(branch_platform.reviews.count(), MAX_REVIEWS_UNDER_TEST)
        remaining_contents = list(branch_platform.reviews.order_by("published_date").values_list("content", flat=True))
        self.assertEqual(remaining_contents, ["Content 2", "Content 3", "Content 4"])

    def test_does_not_delete_reviews_from_other_platform(self) -> None:
        branch_platform = self._make_branch_platform(inn="111111111111")
        other_platform = self._make_branch_platform(inn="222222222222")
        self._create_reviews(branch_platform, count=5)
        self._create_reviews(other_platform, count=5)

        _delete_overflow_reviews(branch_platform.id)

        self.assertEqual(branch_platform.reviews.count(), MAX_REVIEWS_UNDER_TEST)
        self.assertEqual(other_platform.reviews.count(), 5)
