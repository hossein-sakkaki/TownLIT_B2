# apps/profiles/tests/test_organization_projection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-13.
# Last Update by Hossein Sakkaki on 2026-09-13.
#

from django.core.exceptions import FieldDoesNotExist
from django.test import SimpleTestCase

from apps.organizations.models import Organization
from apps.profiles.models import Member
from apps.profiles.serializers.organization import (
    ProfileOrganizationSerializer,
)


class ProfileOrganizationSerializerTests(
    SimpleTestCase
):
    def test_profile_organization_contract(self):
        organization = Organization(
            id=42,
            name="TownLIT Test Organization",
            slug="townlit-test-organization",
        )

        data = ProfileOrganizationSerializer(
            organization
        ).data

        self.assertEqual(
            data,
            {
                "id": 42,
                "org_name": (
                    "TownLIT Test Organization"
                ),
                "slug": (
                    "townlit-test-organization"
                ),
            },
        )

    def test_member_has_no_legacy_organization_m2m(self):
        with self.assertRaises(
            FieldDoesNotExist
        ):
            Member._meta.get_field(
                "organization_memberships"
            )