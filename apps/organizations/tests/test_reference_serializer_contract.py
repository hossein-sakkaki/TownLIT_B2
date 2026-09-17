# apps/organizations/tests/test_reference_serializer_contract.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.test import SimpleTestCase

from apps.organizations.models import Organization
from apps.organizations.serializers import (
    OrganizationReferenceSerializer,
)


class OrganizationReferenceSerializerContractTests(
    SimpleTestCase
):
    def test_reference_payload_preserves_existing_transport_contract(
        self,
    ):
        organization = Organization(
            id=42,
            name="Example Organization",
            slug="example-organization",
        )

        payload = OrganizationReferenceSerializer(
            organization,
            context={},
        ).data

        self.assertEqual(
            payload,
            {
                "id": 42,
                "org_name": "Example Organization",
                "organization_logo": None,
                "slug": "example-organization",
            },
        )