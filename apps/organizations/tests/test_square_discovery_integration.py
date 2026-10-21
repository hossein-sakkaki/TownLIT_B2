# apps/organizations/tests/test_square_discovery_integration.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organizations.constants import (
    OrganizationKind,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import Organization
from apps.organizations.views.discovery import OrganizationDiscoveryView
from apps.subscriptions.models import SubscriptionAccount


@override_settings(TOWNLIT_ORGANIZATIONS_ENABLED=True)
class SquareOrganizationDiscoveryIntegrationTests(TestCase):
    """Square reuses the Organization-owned discovery API."""

    def setUp(self):
        self.viewer = get_user_model().objects.create_user(
            email="square-discovery@townlit.test",
            password="test-password",
        )
        self.factory = APIRequestFactory()

    def organization(self, name, slug, visibility=OrganizationVisibility.PUBLIC):
        return Organization.objects.create(
            name=name,
            slug=slug,
            kind=OrganizationKind.NONPROFIT,
            status=OrganizationStatus.ACTIVE,
            visibility=visibility,
            subscription_account=SubscriptionAccount.objects.create(),
        )

    def search(self, query):
        request = self.factory.get("/api/v1/organizations/discovery/", {"q": query})
        force_authenticate(request, user=self.viewer)
        response = OrganizationDiscoveryView.as_view()(request)
        response.render()
        return response

    def test_public_active_organization_is_returned_by_name(self):
        self.organization("TownLIT Society", "townlit-society")

        response = self.search("townlit")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "townlit-society")
        self.assertEqual(response.data["results"][0]["name"], "TownLIT Society")

    def test_unlisted_organization_is_not_discoverable(self):
        self.organization(
            "Hidden Community",
            "hidden-community",
            visibility=OrganizationVisibility.UNLISTED,
        )

        response = self.search("hidden")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_short_query_does_not_return_organizations(self):
        self.organization("TownLIT Society", "townlit-society")

        response = self.search("t")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
