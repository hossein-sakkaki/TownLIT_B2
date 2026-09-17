# apps/organizations/tests/test_creation_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-12.
# Last Update by Hossein Sakkaki on 2026-09-12.
#

from inspect import signature

from django.test import SimpleTestCase

from apps.organizations.constants import (
    OrganizationKind,
    OrganizationVisibility,
)
from apps.organizations.serializers import (
    OrganizationWriteSerializer,
)
from apps.organizations.services.creation import (
    create_organization,
)


class OrganizationCreationContractTests(SimpleTestCase):

    def test_write_serializer_payload_binds_to_creation_service(self):
        serializer = OrganizationWriteSerializer(
            data={
                "name": "TownLIT Test Organization",
                "kind": OrganizationKind.MINISTRY,
                "visibility": OrganizationVisibility.PRIVATE,
            }
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )
        self.assertEqual(
            serializer.validated_data["visibility"],
            OrganizationVisibility.PRIVATE,
        )

        signature(create_organization).bind(
            creator=object(),
            **serializer.validated_data,
        )

    def test_creation_service_defaults_visibility_to_public(self):
        visibility_parameter = signature(
            create_organization
        ).parameters["visibility"]

        self.assertEqual(
            visibility_parameter.default,
            OrganizationVisibility.PUBLIC,
        )