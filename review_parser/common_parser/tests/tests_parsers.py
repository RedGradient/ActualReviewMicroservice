from unittest.mock import Mock, patch

from django.test import TestCase

from common_parser.models import Branch, BranchPlatform, Organization
from common_parser.parsers import (
    REVIEW_PARSERS,
    REVIEW_PARSERS_BY_PROVIDER,
    get_review_parser,
)
from common_parser.tools.parse import parse_all_providers
from common_parser.types import ParseResult
from common_parser.parsers.vlru.parser import VlruParser
from common_parser.parsers.twogis.parser import TwoGisParser


class RegistryTests(TestCase):
    def test_review_parsers_contains_2gis_and_vlru(self) -> None:
        providers = {parser.provider for parser in REVIEW_PARSERS}
        self.assertEqual(providers, {"2gis", "vlru"})

    def test_get_review_parser(self) -> None:
        self.assertIsInstance(get_review_parser("2gis"), TwoGisParser)
        self.assertIsInstance(get_review_parser("vlru"), VlruParser)

    def test_get_review_parser_unknown_raises(self) -> None:
        with self.assertRaises(KeyError):
            get_review_parser("unknown")

    def test_parser_providers(self) -> None:
        self.assertEqual(REVIEW_PARSERS_BY_PROVIDER["2gis"].provider, "2gis")
        self.assertEqual(REVIEW_PARSERS_BY_PROVIDER["vlru"].provider, "vlru")


class TwoGisParserTests(TestCase):
    @patch("common_parser.parsers.twogis.parser.create_2gis_reviews", return_value=(10, 3))
    def test_run_delegates_to_create_2gis_reviews(self, mock_create) -> None:
        parser = TwoGisParser()

        result = parser.run(
            url="https://2gis.ru/firm/12345",
            inn="123456789012",
            org_name="Org",
            address="Addr",
            limit=20,
        )

        self.assertEqual(result, ParseResult(10, 3))
        mock_create.assert_called_once_with(
            url="https://2gis.ru/firm/12345",
            inn="123456789012",
            org_name="Org",
            address="Addr",
            count=20,
        )


class VlruParserTests(TestCase):
    @patch("common_parser.parsers.vlru.parser.create_vlru_reviews", return_value=(5, 2))
    def test_run_delegates_to_create_vlru_reviews(self, mock_create) -> None:
        client = Mock()
        parser = VlruParser(client=client)

        result = parser.run(
            url="https://www.vl.ru/trinity",
            inn="123456789012",
            org_name="Org",
            address="Addr",
            limit=30,
        )

        self.assertEqual(result, ParseResult(5, 2))
        mock_create.assert_called_once_with(
            url="https://www.vl.ru/trinity",
            inn="123456789012",
            org_name="Org",
            address="Addr",
            count=30,
            client=client,
        )


class ParseAllProvidersTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        org = Organization.objects.create(inn="123456789012", name="Org")
        cls.branch = Branch.objects.create(organization=org, address="Addr")
        BranchPlatform.objects.create(
            branch=cls.branch,
            provider="2gis",
            url="https://2gis.ru/firm/12345",
        )
        BranchPlatform.objects.create(
            branch=cls.branch,
            provider="vlru",
            url="https://www.vl.ru/trinity",
        )

    @patch("common_parser.tools.parse.REVIEW_PARSERS", new_callable=list)
    def test_runs_parsers_for_configured_platforms(self, mock_parsers) -> None:
        twogis = Mock()
        twogis.provider = "2gis"
        twogis.run.return_value = ParseResult(3, 2)
        vlru = Mock()
        vlru.provider = "vlru"
        vlru.run.return_value = ParseResult(5, 1)
        mock_parsers.extend([twogis, vlru])

        results = parse_all_providers(self.branch)

        self.assertEqual(results["tryes"], 2)
        self.assertEqual(results["success"], 2)
        self.assertEqual(results["2gis"], ParseResult(3, 2))
        self.assertEqual(results["vlru"], ParseResult(5, 1))
        twogis.run.assert_called_once_with(
            url="https://2gis.ru/firm/12345",
            inn="123456789012",
            org_name="Org",
            address="Addr",
        )
        vlru.run.assert_called_once_with(
            url="https://www.vl.ru/trinity",
            inn="123456789012",
            org_name="Org",
            address="Addr",
        )

    @patch("common_parser.tools.parse.REVIEW_PARSERS", new_callable=list)
    def test_skips_parser_without_platform_url(self, mock_parsers) -> None:
        branch = Branch.objects.create(
            organization=self.branch.organization,
            address="No VL",
        )
        BranchPlatform.objects.create(
            branch=branch,
            provider="2gis",
            url="https://2gis.ru/firm/999",
        )

        twogis = Mock()
        twogis.provider = "2gis"
        twogis.run.return_value = ParseResult(1, 1)
        vlru = Mock()
        vlru.provider = "vlru"
        mock_parsers.extend([twogis, vlru])

        results = parse_all_providers(branch)

        self.assertEqual(results["tryes"], 1)
        self.assertEqual(results["success"], 1)
        twogis.run.assert_called_once()
        vlru.run.assert_not_called()
