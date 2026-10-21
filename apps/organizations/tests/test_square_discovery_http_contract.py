# apps/organizations/tests/test_square_discovery_http_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

"""Organization discovery HTTP/contract checks without creating a test DB.

These tests use in-memory Organization instances and mock ORM search execution.
They do NOT verify the actual contents of a deployed database.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.http import QueryDict
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organizations.constants import (
    OrganizationKind,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import Organization
from apps.organizations.serializers.discovery import OrganizationDiscoveryQuerySerializer
from apps.organizations.selectors.discovery import (
    OrganizationDiscoveryFilters,
    OrganizationDiscoveryService,
)
from apps.organizations.views.discovery import OrganizationDiscoveryView


@override_settings(TOWNLIT_ORGANIZATIONS_ENABLED=True)
class SquareOrganizationDiscoveryHTTPContractTests(SimpleTestCase):
    """Run via manage.py test with no database creation or writes."""

    URL = "/api/v1/organizations/discovery/"
    databases = set()

    def setUp(self):
        self.factory = APIRequestFactory()
        # DRF force_authenticate accepts a stand-in authenticated principal.
        self.viewer = SimpleNamespace(
            pk=1,
            is_authenticated=True,
            is_active=True,
        )

    def _get(self, params, *, authenticated=True):
        request = self.factory.get(self.URL, params)
        if authenticated:
            force_authenticate(request, user=self.viewer)
        return resolve(self.URL).func(request)

    @staticmethod
    def _organization():
        # An UNSAVED model: no SELECT, INSERT or subscription account is needed.
        organization = Organization(
            id=39,
            name="TownLIT Society",
            slug="townlit-society",
            kind=OrganizationKind.NONPROFIT,
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
            activity_areas=["community", "education"],
        )
        # Prevent the verification serializer from consulting the database.
        organization._discovery_is_verified = False
        return organization

    def test_route_resolves_to_discovery_view(self):
        self.assertIs(
            resolve(self.URL).func.view_class,
            OrganizationDiscoveryView,
        )

    def test_authenticated_search_returns_paginated_contract(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
            return_value=[self._organization()],
        ) as mocked_search:
            response = self._get({"q": "TownLIT", "page": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNone(response.data["next"])
        self.assertEqual(response.data["results"][0]["slug"], "townlit-society")
        self.assertEqual(response.data["results"][0]["name"], "TownLIT Society")
        self.assertIsInstance(
            response.data["results"][0]["activity_areas"], list
        )
        self.assertIn("public_id", response.data["results"][0])
        self.assertIs(response.data["results"][0]["is_verified"], False)
        self.assertEqual(
            response["X-TownLIT-Discovery-Ranking"],
            "organization.discovery.v1",
        )
        self.assertEqual(mocked_search.call_args.kwargs["query"], "TownLIT")

    def test_multiword_query_reaches_search_service(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
            return_value=[],
        ) as mocked_search:
            response = self._get({"q": "TownLIT Society"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(
            mocked_search.call_args.kwargs["query"],
            "TownLIT Society",
        )

    def test_base_queryset_requires_active_and_public(self):
        # Inspect the actual ORM filter call without executing a SQL query.
        fake_queryset = MagicMock()
        fake_queryset.annotate.return_value = fake_queryset
        with patch.object(
            Organization.objects,
            "filter",
            return_value=fake_queryset,
        ) as mocked_filter:
            result = OrganizationDiscoveryService._base_queryset(
                filters=OrganizationDiscoveryFilters()
            )

        mocked_filter.assert_called_once_with(
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
        )
        self.assertIs(result, fake_queryset)

    def test_short_query_exits_before_database_access(self):
        with patch.object(
            OrganizationDiscoveryService,
            "_base_queryset",
        ) as mocked_queryset:
            result = OrganizationDiscoveryService.search(query="T")

        self.assertEqual(result, [])
        mocked_queryset.assert_not_called()

    @override_settings(TOWNLIT_ORGANIZATIONS_ENABLED=False)
    def test_disabled_feature_denies_search_without_query(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
        ) as mocked_search:
            response = self._get({"q": "TownLIT"})

        self.assertEqual(response.status_code, 403)
        mocked_search.assert_not_called()

    def test_verified_filter_omission_keeps_both_verification_states(self):
        # APIRequestFactory produces a QueryDict, unlike a plain Python dict.
        with patch.object(
            OrganizationDiscoveryService,
            "search",
            return_value=[],
        ) as mocked_search:
            response = self._get({"q": "TownLIT", "page": 1})

        self.assertEqual(response.status_code, 200)
        passed_filters = mocked_search.call_args.kwargs["filters"]
        self.assertIsNone(passed_filters.verified)
        self.assertFalse(passed_filters.has_any_filter)

    def test_serializer_omitted_verified_is_not_false(self):
        params = QueryDict("q=TownLIT&page=1")
        serializer = OrganizationDiscoveryQuerySerializer(data=params)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get("verified"))

    def test_explicit_verified_true_filters_for_verified(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
            return_value=[],
        ) as mocked_search:
            response = self._get({"q": "TownLIT", "verified": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertIs(
            mocked_search.call_args.kwargs["filters"].verified,
            True,
        )

    def test_explicit_verified_false_filters_for_unverified(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
            return_value=[],
        ) as mocked_search:
            response = self._get({"q": "TownLIT", "verified": "false"})

        self.assertEqual(response.status_code, 200)
        self.assertIs(
            mocked_search.call_args.kwargs["filters"].verified,
            False,
        )

    def test_explicit_verified_blank_keeps_all(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
            return_value=[],
        ) as mocked_search:
            response = self._get({"q": "TownLIT", "verified": ""})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            mocked_search.call_args.kwargs["filters"].verified,
        )

    def test_invalid_verified_returns_http_400(self):
        with patch.object(
            OrganizationDiscoveryService,
            "search",
        ) as mocked_search:
            response = self._get({"q": "TownLIT", "verified": "invalid"})

        self.assertEqual(response.status_code, 400)
        mocked_search.assert_not_called()

