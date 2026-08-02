import unittest
from datetime import datetime, timedelta

from rest_framework.test import APITestCase

from common_parser.models import Branch, BranchIPMapping, BranchPlatform, Organization, Review


@unittest.skip
class ReviewsApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        org = Organization.objects.create(inn="123456789012", name="Org")
        cls.branch = Branch.objects.create(
            organization=org,
            address="Addr",
        )
        cls.yandex_platform = BranchPlatform.objects.create(
            branch=cls.branch,
            provider="yandex",
            url="https://yandex.ru/maps/org/x",
        )
        cls.vlru_platform = BranchPlatform.objects.create(
            branch=cls.branch,
            provider="vlru",
            url="https://www.vl.ru/test",
        )

        Review.objects.create(
            branch_platform=cls.yandex_platform,
            author="a1",
            rating=3,
            content="c1",
            published_date=datetime.now() - timedelta(days=2),
        )
        Review.objects.create(
            branch_platform=cls.yandex_platform,
            author="a2",
            rating=5,
            content="c2",
            published_date=datetime.now() - timedelta(days=1),
        )
        Review.objects.create(
            branch_platform=cls.vlru_platform,
            author="v1",
            rating=4,
            content="vc1",
            published_date=datetime.now(),
        )

        BranchIPMapping.objects.create(branch=cls.branch, ip_address="1.2.3.4")

    def test_get_reviews_v1_basic_and_pagination(self) -> None:
        resp = self.client.get("/api/common/get_reviews/", {"branch_id": self.branch.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("reviews", resp.data)

        resp2 = self.client.get(
            "/api/common/get_reviews/",
            {"branch_id": self.branch.id, "limit": 1, "offset": 0},
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data["reviews"]), 1)

    def test_reviews_v2_providers_csv_only_providers(self) -> None:
        resp = self.client.get(
            "/api/common/v2/reviews",
            {
                "branch_id": self.branch.id,
                "providers": "yandex,vlru",
                "count_yandex": 1,
                "only_providers": "true",
            },
        )
        self.assertEqual(resp.status_code, 200)
        reviews = resp.data["reviews"]
        self.assertEqual(len(reviews), 2)
        self.assertIn("yandex", reviews)
        self.assertIn("vlru", reviews)
        self.assertEqual(len(reviews["yandex"]), 1)
        self.assertEqual(len(reviews["vlru"]), 1)

    def test_reviews_v2_provider_filters(self) -> None:
        resp = self.client.get(
            "/api/common/v2/reviews",
            {
                "branch_id": self.branch.id,
                "providers": "yandex",
                "filters_yandex": "rating__gt=4",
                "only_providers": "true",
            },
        )
        self.assertEqual(resp.status_code, 200)
        yandex_reviews = resp.data["reviews"]["yandex"]
        self.assertTrue(all(float(r["rating"]) > 4 for r in yandex_reviews))

    def test_reviews_by_ip_v2(self) -> None:
        resp = self.client.get(
            "/api/common/v2/reviews_by_ip",
            {},
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("branches", resp.data)
        self.assertGreaterEqual(len(resp.data["reviews"]), 1)
